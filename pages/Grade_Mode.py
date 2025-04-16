import streamlit as st
import serial
import time
import requests
import google.generativeai as genai
import re

GEMINI_API_KEY = "AIzaSyDmcJIFbYkvoxSYtS7P7qa0V8TK428NVLc"


genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

arduino = serial.Serial("/dev/tty.usbmodem14101", 9600, timeout=1)


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
                    circuitID = race['Circuit']['circuitId'].lower()

                    if (gp.lower() == circuitID):
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

def fetch_current_data():
    constructorsURL = f"https://api.jolpi.ca/ergast/f1/2025/constructors.json?limit=1000"
    driversURL = f"https://api.jolpi.ca/ergast/f1/2025/drivers.json?limit=1000"
    currentSeasonURL = f"https://api.jolpi.ca/ergast/f1/2025/results.json?limit=1000"
    currentRacesURL = f"https://api.jolpi.ca/ergast/f1/2025/circuits.json?limit=1000"
    currentDrivers = []
    currentTeams = []
    currentResults = []
    currentRaces = []

    races_response = requests.get(currentRacesURL)
    if races_response.status_code == 200:
        allRaces = races_response.json()['MRData']['CircuitTable']['Circuits']
        for race in allRaces:
            circuit_info = {
                'circuitId': race['circuitId'],
                'circuitName': race['circuitName'],
                'locality': race['Location']['locality'],
                'country': race['Location']['country']
            }
            currentRaces.append(circuit_info)
    else:
        st.error("Error fetching circuit data.")

    constructors_response = requests.get(constructorsURL)
    if constructors_response.status_code == 200:
        allConstructors = constructors_response.json()['MRData']['ConstructorTable']['Constructors']
        for constructor in allConstructors:
            currentTeams.append(constructor['name'])
    else:
        st.error("Error fetching constructors data.")

    drivers_response = requests.get(driversURL)
    if drivers_response.status_code == 200:
        allDrivers = drivers_response.json()['MRData']['DriverTable']['Drivers']
        for driver in allDrivers:
            currentDrivers.append(driver['givenName'] + " " + driver['familyName'] + " " + driver['permanentNumber'])        
    else:
        st.error("Error fetching drivers data.")
    
    results_response = requests.get(currentSeasonURL)
    if results_response.status_code == 200:
        currentResults = results_response.json()['MRData']['RaceTable']['Races']
    else:
        st.error("Error fetching race results data.")

    allCurrentData = {
        'allConstructors': allConstructors,
        'constructorsName': currentTeams,
        'allDrivers': allDrivers,
        'driversName': currentDrivers,
        'results': currentResults,
        'races': currentRaces
    }
    return allCurrentData

currentData = fetch_current_data()
constructors = currentData['constructorsName']
drivers = currentData['driversName']
races = currentData['races']

def fetch_fantasy_data():
    """Fetch live fantasy data for drivers and constructors."""
    drivers_url = "https://fantasy.formula1.com/feeds/statistics/drivers_3.json"
    constructors_url = "https://fantasy.formula1.com/feeds/statistics/constructors_3.json"
    
    headers = {"User-Agent": "Mozilla/5.0"}  # Mimic a real browser request
    
    try:
        drivers_data = []
        constructors_data = []
        raw_drivers_data = requests.get(drivers_url, headers=headers).json()
        raw_constructors_data = requests.get(constructors_url, headers=headers).json()
        for driver in raw_drivers_data["Data"]["statistics"][0]["participants"]:
            driver_info = {
                "playername": driver["playername"],
                "curvalue": driver["curvalue"]
                }
            drivers_data.append(driver_info)
        for team in raw_constructors_data["Data"]["statistics"][0]["participants"]:
            team_info = {
                "teamname": team["teamname"],
                "curvalue": team["curvalue"]
                }
            constructors_data.append(team_info)

        all_fantasy_data = { "drivers_data" : drivers_data, "constructors_data": constructors_data}
        return all_fantasy_data
    except Exception as e:
        print("Error fetching F1 Fantasy data:", e)
        return None

all_fantasy_data = fetch_fantasy_data()

def gemini_recommend(ciruitId,chosen_constructors,chosen_drivers,drs_boost):
    trackContext = fetch_past_data(ciruitId)
    if not trackContext:
        st.warning(f"No data found for the Grand Prix: {gp}. Please try a different one.")
        return
    st.session_state.trackContext = trackContext
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

    You are grading the user's F1 Fantasy Team for the {trackContext[0]["Race"]} at the {trackContext[0]["Circuit"]}.
    The user's constructors are {chosen_constructors}, their drivers are {chosen_drivers}, and their driver with the DRS Boost is {drs_boost}.
    
    **The purpose of DRS Boost:** Any driver can receive the **DRS Boost**, which **doubles their score** for that race.
    
    Use the results from 2020-2024 to look at the user's team: {raceResults}. You can find this year's results at {currentData['races']}.
    The cost of each team can be calculated by adding the cost of each driver and constructor on the team. You can find this information at {all_fantasy_data}.
    Give them a score from 1 to 5 based on how succesful you think their team will be, how efficiently they're using their budget, and how well those constructors and drivers have done historically and this season. 

    After that, recommend some changes for their team. 
    Make sure any driver change you recommend or constructor change you recommend is on the grid this year.
    You can get that from {drivers}, {constructors}, {currentDriversURL}, and {currentTeamsURL}. 
    You can also recommend the user changes which driver they give their DRS boost to based on previous race results: {raceResults}.
    Remember there is a cost cap of 100. So any driver/constructor you recommend should not change the total cost of the whole team to be greater than 100.
    You can get this cost data from {all_fantasy_data}.
    If you happen recommend a change, then also mention how much the new team costs and how much this new driver/constructor costs.


    This should be the format for the returned text:
    1. **User's Team**
    - their team info here (include constructors, drivers, DRS boost, and the cost)
    2. **Score (from 1-5)**
    - Score: 
    -write a short paragraph explaining why they got it
    3. **Recommendations**
    - suggest changes that they can make - provide them with three alternative team options

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
    Some other information from the F1 Fantasy website and just F1 knowledge:
    - **Chips:** F1® Teams bring upgrades for their cars, and fantasy players can use chips to power up their team. 
      There are six chips available (one use per season), including a **x3 multiplier chip**.
    - **DRS Boost:** Any driver can receive the **DRS Boost**, which **doubles their score** for that race.
    - **Rookie:** A rookie is any driver who hasn't completed their first full season in F1.

    You have a recommendation for the F1 Fantasy team:
    **{recommendation}**

    You also have the following chat history with the user:
    **{chat_history_str}**
    
    Previous race results:
    {raceResults}

    Available years for reference:
    {availableYears}

    Track context:
    {trackContext}

    Statistics from F1 Fantasy:
    {all_fantasy_data}

    The information about this track and results here are:
    
    All the data about the current season can be found below:
    - {allCurrentData} all general data including race results
    - {currentTeamsURL} for all the constructors
    - {currentDriversURL} for all the drivers

    Now, answer the new question with this information: 
    **{otherQs}**

    Use the past race data and current season data to respond optimally.
    """
    response = model.generate_content(prompt)
    return response.text

def send_score_to_arduino(score):
    arduino.write(str(score).encode())
    time.sleep(1)

def display_recommendation(response_text):

    st.subheader("🏎️ Your F1 Fantasy Team Grade and Recommendations")

    try:
        team_section = response_text.split("1. **User's Team**")[1].split("2. **Score (from 1-5)**")[0].strip()
        score_section = response_text.split("2. **Score (from 1-5)**")[1].split("3. **Recommendations**")[0].strip()
        recommendations_section = response_text.split("3. **Recommendations**")[1].strip()
    except IndexError:
        st.error("⚠️ Could not parse the AI response properly. Please ensure the format is consistent.")
        return

    match = re.search(r"Score:\s*(\d+)", score_section)
    if match:
        score_int = int(match.group(1))
        st.session_state.team_score = score_int
        send_score_to_arduino(score_int)
    else:
        st.error("⚠️ Could not extract a valid score from the AI's response.")
        return

    st.markdown("##### :blue-background[ 🧾 User's Team]")
    st.markdown(team_section, unsafe_allow_html=True)

    st.markdown("##### :blue-background[ 📊 Score & Justification]")
    st.markdown(score_section, unsafe_allow_html=True)

    st.markdown("##### :blue-background[ 📈 Recommendations]")
    st.markdown(recommendations_section, unsafe_allow_html=True)


def submit_clarifying():
    st.session_state.chat_history.append(("User", st.session_state.clarifying_input))
    clarification_response = gemini_chat(st.session_state.recommendation, st.session_state.clarifying_input)
    st.session_state.chat_history.append(("Bot", clarification_response))
    
    st.session_state.clarifying_input = ""

st.set_page_config(
    layout="wide",
    initial_sidebar_state="collapsed"
)

col1, col2 = st.columns(2)

with col1:
    st.page_link("Home.py", label=":grey-background[:house: Go Home]")

with col2:
    st.page_link("pages/Create_Mode.py", label=":grey-background[:triangular_ruler: Go to Create Mode]")
st.divider()
st.title(":red[:memo: F1 Fantasy: Grade Mode]")
if st.button("🔄 Reset and Start New Request"):
    keys_to_clear = ["gp_input", "specifics_input", "recommendation", "chat_history", 
                     "clarifying_input", "trackContext", "allCurrentData", 
                     "raceResults", "availableYears"]
    
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    st.rerun()

st.markdown(":orange[**Which race do you want me to grade?**]")
gp = st.text_input("Please only put the commonly known name of the location of the race. Eg. Miami, Australia, etc.", placeholder="Australia", key="gp_input")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


if gp:
    raceFound = False
    for race in races:
        if (gp.lower() in race['circuitId'].lower()
            or gp.lower() in race['circuitName'].lower()
            or gp.lower() in race['locality'].lower()
            or gp.lower() in race['country'].lower()
        ):
            ciruitId = race['circuitId']
            raceFound = True
            break
    if raceFound:
        st.markdown(":orange[**Please choose the drivers and constructors on your team**]")
        chosen_constructors = st.multiselect ("Select the 2 constructors on your team:", 
        options=constructors, 
        default=[], 
        max_selections=2)

        chosen_drivers = st.multiselect ("Select 5 drivers on your team:", 
        options=drivers, 
        default=[], 
        max_selections=5)

        drs_boost = st.multiselect ("Select which driver has your DRS boost:", 
        options=chosen_drivers + ["None"], 
        default=[], 
        max_selections=1)
        if "recommendation" not in st.session_state:
            st.session_state.recommendation = None

        if st.button("Submit Team"):
            if len(chosen_drivers) == 5 and len(chosen_constructors) == 2 and len(drs_boost) == 1:
                st.write("Team submitted successfully! 🏎️🔥")
                with st.spinner("Grading your team..."):
                    recommendation = gemini_recommend(ciruitId,chosen_constructors,chosen_drivers,drs_boost)

                if "clarifying_input" not in st.session_state:
                    st.session_state.clarifying_input = ""
                st.markdown(":orange[**Would you like to ask any follow-up questions?**]")
                clarifying_question = st.text_input(
                    "Ask any follow-up questions", placeholder= "I don't like xxx driver. Who can I replace them with?",
                    key="clarifying_input", on_change=submit_clarifying)   
                      
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

                st.markdown("### 💬 Conversation History")

                history_pairs = list(zip(st.session_state.chat_history[::2], st.session_state.chat_history[1::2]))

                for (user_msg, bot_msg) in reversed(history_pairs):
                    st.markdown(f":violet[:speech_balloon: **{user_msg[0]}:**] {user_msg[1]}")
                    st.markdown(f":violet[:robot_face: **{bot_msg[0]}:**] {bot_msg[1]}")                       
                if "recommendation" in st.session_state:
                    st.divider()
                    st.text("Here is your recommended team:")
                    st.session_state.recommendation = recommendation
                    display_recommendation(st.session_state.recommendation)
            else:
                st.warning("You haven't chosen a full team. Please make sure pick the right number of drivers, constructors, and one option in the DRS Boost section.")

    else:
        st.warning("The race name you inputed doesn't exist. Please make sure it's typed right and there actually is a GP at that track this year.")

else:
    st.warning("You must select a race in order to proceed.")