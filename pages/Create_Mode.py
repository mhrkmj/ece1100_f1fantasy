import streamlit as st
import requests
import google.generativeai as genai

GEMINI_API_KEY = "AIzaSyDmcJIFbYkvoxSYtS7P7qa0V8TK428NVLc"

st.set_page_config(
    layout="wide",
    initial_sidebar_state="collapsed"
)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def fetch_past_data(gp):
    year = 2020
    allTrackData = []
    numRaces = 0
    while year < 2025:
        offset = 0
        while True:
            f1url = f"http://api.jolpi.ca/ergast/f1/{year}/results.json?format=api&limit=30&offset={offset}"
            response = requests.get(f1url)
            if response.status_code == 200:
                data = response.json()
                races = data['MRData']['RaceTable']['Races']
                if not races:
                    break
                foundRace = False

                for race in races:
                    raceName = race['raceName'].lower()
                    circuitName = race['Circuit']['circuitName'].lower()
                    circuitID = race['Circuit']['circuitId'].lower()

                    if (gp.lower() == circuitID or
                        gp.lower() in raceName or
                        gp.lower() in circuitName):
                        foundRace = True
                        race_data = {
                            "Season": year,
                            "Race": race['raceName'],
                            "Date": race['date'],
                            "Circuit": race['Circuit']['circuitName'],
                            "Results": []
                        }
                        for result in race['Results']:
                            driver_result = {
                                "Driver": f"{result['Driver']['givenName']} {result['Driver']['familyName']}",
                                "Constructor": result['Constructor']['name'],
                                "Position": result.get('position', 'N/A'),
                                "Points": result.get('points', 'N/A')
                            }
                            race_data["Results"].append(driver_result)
                        allTrackData.append(race_data)
                        numRaces += 1
                offset += 30
        year += 1
    if numRaces == 0:
        st.warning(f"No races found for {gp} from 2019 to 2024.")
    return allTrackData

def fetch_current_data(gp):
    constructorsURL = f"https://api.jolpi.ca/ergast/f1/2025/constructors.json?limit=1000"
    driversURL = f"https://api.jolpi.ca/ergast/f1/2025/drivers.json?limit=1000"
    currentSeasonURL = f"https://api.jolpi.ca/ergast/f1/2025/results.json?limit=1000"
    currentDrivers = []
    currentTeams = []
    currentResults = []

    constructors_response = requests.get(constructorsURL)
    if constructors_response.status_code == 200:
        currentTeams = constructors_response.json()['MRData']['ConstructorTable']['Constructors']
    else:
        st.error("Error fetching constructors data.")

    drivers_response = requests.get(driversURL)
    if drivers_response.status_code == 200:
        currentDrivers = drivers_response.json()['MRData']['DriverTable']['Drivers']
    else:
        st.error("Error fetching drivers data.")
    
    results_response = requests.get(currentSeasonURL)
    if results_response.status_code == 200:
        currentResults = results_response.json()['MRData']['RaceTable']['Races']
    else:
        st.error("Error fetching race results data.")

    allCurrentData = {
        'constructors': currentTeams,
        'drivers': currentDrivers,
        'results': currentResults
    }
    return allCurrentData

def fetch_fantasy_data():
    """Fetch live fantasy data for drivers and constructors."""
    drivers_url = "https://fantasy.formula1.com/feeds/statistics/drivers_3.json"
    constructors_url = "https://fantasy.formula1.com/feeds/statistics/constructors_3.json"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        drivers_data = []
        constructors_data = []
        raw_drivers_data = requests.get(drivers_url, headers=headers).json()
        raw_constructors_data = requests.get(constructors_url, headers=headers).json()
        for driver in raw_drivers_data["Data"]["statistics"][0]["participants"]:
            driver_info = {
                "playername": driver["playername"],
                "curvalue": driver["curvalue"],
                "statvalue": driver["statvalue"]
                }
            drivers_data.append(driver_info)
        for team in raw_constructors_data["Data"]["statistics"][0]["participants"]:
            team_info = {
                "teamname": team["teamname"],
                "curvalue": team["curvalue"],
                "statvalue": team["statvalue"]
                }
            constructors_data.append(team_info)

        all_fantasy_data = { "drivers_data" : drivers_data, "constructors_data": constructors_data}
        return all_fantasy_data
    except Exception as e:
        print("Error fetching F1 Fantasy data:", e)
        return None

all_fantasy_data = fetch_fantasy_data()

def gemini_recommend(gp,specifics):
    trackContext = fetch_past_data(gp)
    allCurrentData = fetch_current_data(gp)
    if not trackContext:
        st.warning(f"No data found for the Grand Prix: {gp}. Please try a different one.")
        return
    st.session_state.trackContext = trackContext
    st.session_state.allCurrentData = allCurrentData    
    availableYears = [str(year) for year in range(2020, 2025) if any(race['Season'] == year for race in trackContext)]
    
    raceResults = ""
    for year in availableYears:
        raceDataForYear = [race for race in trackContext if str(race['Season']) == year]
        raceResults += f"The results in {year} were: {raceDataForYear[0]['Results']}.\n"

    st.session_state.raceResults = raceResults
    st.session_state.availableYears = availableYears

    currentDriversURL = "https://www.formula1.com/en/drivers"
    currentTeamsURL = "https://www.formula1.com/en/teams"

    prompt = f"""
    You are a F1 Fantasy Player making a team for the {trackContext[0]["Race"]} at the {trackContext[0]["Circuit"]}. 
    AS A REMINDER YOU TEAM CANNOT COST MORE THAN 100. 
    Use the results from 2020-2024 to help the user create the best fantasy team possible. 
    {raceResults}
    **EVERTYTHINK YOU RETURN OUT MUST BE TEXT. DON'T PRINT ANY VARIABLES**
    Based on this information, give the user five drivers and two constructors for their team. 
    Make sure that the drivers and teams you recommend actually exist by getting the information from the following links:.
    The user may have specific requests. Make sure that you accomplish their requests which are {specifics}. 
    YOU MUST FULFILL THEIR SPECIFIC REQUEST. THE ONLY WAY YOU CAN GET AWAY WITH NOT DOING IT IF THEY ASK FOR A DRIVER OR TEAM THAT IS NO LONGER ON THE GRID.
    Make sure to only return drivers who are currently on the grid. You can get that information from here: {allCurrentData["drivers"]} and at {currentDriversURL}.
    Also make sure you have the right team names, which you can find here: {allCurrentData["constructors"]} and also {currentTeamsURL}.
    You can also data/statistics from F1 fantasy to help recommend the teams. you can find this at: {all_fantasy_data['drivers_data']} for driver and constructor data at {all_fantasy_data['constructors_data']}.
    **The name gives you the information about the driver/constructor, the 'curvalue' tells you the cost of the driver/constructor, and lastly 'statvalue' represents the points a driver or constructor gets statistically.**
    Lastly, also MAKE SURE to use the results of the current season to recommend drivers. You can get that info here: {allCurrentData["results"]}.
    You can find driver costs at {all_fantasy_data['drivers_data']} and constructor data at {all_fantasy_data['constructors_data']}.
    
    AGAIN ALL RECOMMENDED DRIVERS MUST BE PRESENTLY DRIVING. DO NOT RECOMMEND SERGIO PEREZ, ZHOU GUANYU, VALTERRI BOTTAS, KEVIN MAGNUSSEN, DANIEL RICCIARDO, OR ANYT OTHER EX DRIVER.

    **EVERTYTHINK YOU RETURN OUT MUST BE TEXT. DON'T PRINT ANY VARIABLES**
    **Return all numbers as part of the text, formatted properly. Example: "$8.5 million" instead of 8.5 or a variable.**

    DO NOT MENTION THE TOTAL COST OF THE TEAM IN THE WHOLE ANSWER

    This should be the format for the returned text:
    1. **Summary**
    - a short summary explaining what data you used
    2. **Recommended Team**
    a. 2 constructors, why they were chosen and their costs. the constructors subtitle should be returned in the format ":blue[ a. Constructors]"
    b. 5 drivers, why they were chosen and their costs. also mention which driver should have the drs boost
    c. add all the costs and give a total cost
    3. **Alternatives**
    - suggest three alternative teams - for example some driver or constructor swaps

    **EVERTYTHINK YOU RETURN OUT MUST BE TEXT. DON'T PRINT ANY VARIABLES**
    """
    response = model.generate_content(prompt)
    return response.text

def gemini_chat(recommendation,otherQs):
    trackContext = st.session_state.trackContext
    allCurrentData = st.session_state.allCurrentData
    raceResults = st.session_state.raceResults
    availableYears = st.session_state.availableYears
    currentDriversURL = "https://www.formula1.com/en/drivers"
    currentTeamsURL = "https://www.formula1.com/en/teams"

    chat_history_str = "\n".join([f"User: {msg[1]}" if msg[0] == "User" else f"Bot: {msg[1]}" for msg in st.session_state.chat_history])


    prompt = f"""
    You are continuing a conversation where the user is trying to build an F1 Fantasy team.
    Some other information from the F1 Fantasy website and just F1 knowledge:
    - **Chips:** F1® Teams bring upgrades for their cars, and fantasy players can use chips to power up their team. 
      There are six chips available (one use per season), including a **x3 multiplier chip**.
    - **DRS Boost:** Any driver can receive the **DRS Boost**, which **doubles their score** for that race.
    - **Rookie:** A rookie is any driver who hasn't completed their first full season in F1.

    Previous conversation:
    {chat_history_str}

    You have a recommendation for the F1 Fantasy team:
    **{recommendation}**

    Previous race results:
    {raceResults}

    Available years for reference:
    {availableYears}

    The context for this track is at:
    {trackContext}

    The information about this track and results here are:
    
    All the data about the current season can be found below:
    - {allCurrentData} all general data including race results
    - {currentTeamsURL} for all the constructors
    - {currentDriversURL} for all the drivers

    YOU CANNOT RECOMMEND A DRIVER THAT'S NOT IN {allCurrentData}. DOING THAT IS ILLEGAL AND IMPOSSIBLE

    Now, answer the new question: 
    **{otherQs}**

    Answer this new question while considering the full conversation history and all the data you have.
    """
    response = model.generate_content(prompt)
    return response.text

def display_recommendation(response_text):
    """
    Parses and displays the AI-generated F1 Fantasy recommendation for CREATE mode.
    Expected sections:
    1. Summary
    2. Recommended Team (with constructors and drivers)
    3. Alternatives
    """

    st.subheader("🏎️ RECOMMENDED FANTASY TEAM")
    summary_section = response_text.split("1. **Summary**")[1].split("2. **Recommended Team**")[0].strip()
    recommended_team_section = response_text.split("2. **Recommended Team**")[1].split("3. **Alternatives**")[0].strip()
    alternatives_section = response_text.split("3. **Alternatives**")[1].strip()

    st.markdown("##### :blue-background[ 📝 Summary]")
    st.markdown(summary_section, unsafe_allow_html=True)

    st.markdown("##### :blue-background[ 🏁 Recommended Team]")
    st.markdown(recommended_team_section, unsafe_allow_html=True)

    st.markdown("##### :blue-background[ 🔄 Alternative Team Ideas]")
    st.markdown(alternatives_section, unsafe_allow_html=True)

def submit_clarifying():
    st.session_state.chat_history.append(("User", st.session_state.clarifying_input))
    clarification_response = gemini_chat(st.session_state.recommendation, st.session_state.clarifying_input)
    st.session_state.chat_history.append(("Bot", clarification_response))
    
    st.session_state.clarifying_input = ""


col1, col2 = st.columns(2)

with col1:
    st.page_link("Home.py", label=":grey-background[:house: Go Home]")

with col2:
    st.page_link("pages/Grade_Mode.py", label=":grey-background[📝 Go to Grade Mode]")

st.divider()
st.title(":red[:triangular_ruler: F1 Fantasy: Create Mode]")
if st.button("🔄 Reset and Start New Request"):
    keys_to_clear = ["gp_input", "specifics_input", "recommendation", "chat_history", 
                     "clarifying_input", "trackContext", "allCurrentData", 
                     "raceResults", "availableYears"]
    
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    st.rerun()
st.markdown("Welcome to the create mode of this program. Here, you can put in which grand prix you want help creating a F1 team for and this program will help you. However, this program does run on the *Gemini API*. This means that it is not good at doing math. So your recommended team's total may be over the $100m cost cap. If that is the case, please just mention it in the clarifying questions sections and the bot will help you think of alternatives. Enjoy and I hope your team does well for the season!")
st.divider()
st.markdown("#### :green-background[ ⌨️ Initial Questions]")    
st.markdown(":orange[**Which race do you need help with?**]")
gp = st.text_input("Please only put the commonly known name of the location of the race. Eg. Miami, Australia, etc.", placeholder="Australia", key="gp_input")
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if gp:
    st.markdown(":orange[**Is there anything else you would like to let the bot know?**]")
    specifics = st.text_input("If you have no specific criteria, then please just put 'n/a'. Here's an example of something you can put here: 'My favorite team is Williams and I would prefer to have at least one of their drivers.'", 
                              placeholder="Type requirements", key="specifics_input")
    
    if specifics:
        if specifics.lower() in ['n/a', 'no specific requests']:
            specifics = "No specific requests."
        with st.spinner('Fetching race data...'):
            if "recommendation" not in st.session_state:  
                st.markdown("*Notice: this program has to sort through a lot of data so it might take a bit for it to recommend a team. Please be patient with it 😌*")
                st.session_state.recommendation = gemini_recommend(gp, specifics)
        
        if "clarifying_input" not in st.session_state:
            st.session_state.clarifying_input = ""
        st.markdown("#### :green-background[ 🤔 Follow-Up/Clarifying Questions]")
        st.markdown(":orange[**Would you like to ask any follow-up questions?**]")
        clarifying_question = st.text_input(
            "Ask any follow-up questions", placeholder= "I don't like xxx driver. Who can I replace them with?",
            key="clarifying_input", on_change=submit_clarifying)
        st.divider()

        if clarifying_question:
            with st.spinner('Processing your question...'):
                if "recommendation" not in st.session_state:
                    st.error("Error: No team recommendation found. Please generate a team first.")
                else:
                    clarification_response = gemini_chat(st.session_state.recommendation, clarifying_question)

                st.session_state.chat_history.append(("User", clarifying_question))
                st.session_state.chat_history.append(("Bot", clarification_response))


            st.markdown(f":violet[**User:**] {clarifying_question}")
            st.markdown(f":violet[**Bot:**] {clarification_response}")

        st.markdown("##### :blue-background[ 💬 Conversation History]")

        history_pairs = list(zip(st.session_state.chat_history[::2], st.session_state.chat_history[1::2]))

        for (user_msg, bot_msg) in reversed(history_pairs):
            st.markdown(f":violet[:speech_balloon: **{user_msg[0]}:**] {user_msg[1]}")
            st.markdown(f":violet[:robot_face: **{bot_msg[0]}:**] {bot_msg[1]}")

        if "recommendation" in st.session_state:
            st.divider()
            display_recommendation(st.session_state.recommendation)

    else:
        st.warning("Please put in a specific requirement for the bot to proceed. Once again, if you have no specific criteria, then please just put 'n/a'")
