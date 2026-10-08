# Soccer Team Builder Simulator. Developed by Zaid Maree.
# This is an app that lets you make your own soccer team by buying players within a budget in the transfer market.
# After finalizing the team, you can simulate a league season by using a specialized UI that shows the league table
# every matchweek along with the stats of your team and the scorelines for each game. The results of the games are
# decided by RNG, but higher attack and defense stats allow a better chance for team success and a higher probability
# of winning the simulated league. This project was coded using python with the Flask web framework.

from flask import Flask, render_template, request, redirect, url_for, session
from players import get_players
from teams import TEAMS
import random

app = Flask(__name__)
app.secret_key = "football_sim_secret"

# --- Helper Functions ---

# Sets prices for each rating
def get_price(rating):
    price_map = {
        97: 120, 96: 110, 95: 105, 94: 100, 93: 95, 92: 90,
        91: 80,  90: 75,  89: 70,  88: 65,  87: 60,  86: 55,
        85: 50,  84: 45,  83: 40,  82: 30,  81: 20,  80: 10
    }
    return price_map.get(rating, 1)

# Calculates the average attack stat of team using both attackers and midfielders' ratings
def calculate_attack(squad):
    if not squad: return 0
    attack_line = (
        (squad["LW"]["rating"] if squad["LW"] else 0) +
        (squad["ST"]["rating"] if squad["ST"] else 0) +
        (squad["RW"]["rating"] if squad["RW"] else 0)
    ) / 3
    midfield = (
        (squad["CM1"]["rating"] if squad["CM1"] else 0) +
        (squad["CM2"]["rating"] if squad["CM2"] else 0) +
        (squad["AM"]["rating"] if squad["AM"] else 0)
    ) / 3
    return round((attack_line * 0.7) + (midfield * 0.3), 1)

# Calculates the average defense stat of team using both defenders and midfielders' ratings
def calculate_defense(squad):
    if not squad: return 0
    defense_line = (
        (squad["LB"]["rating"] if squad["LB"] else 0) +
        (squad["CB1"]["rating"] if squad["CB1"] else 0) +
        (squad["CB2"]["rating"] if squad["CB2"] else 0) +
        (squad["RB"]["rating"] if squad["RB"] else 0) +
        (squad["GK"]["rating"] if squad["GK"] else 0)
    ) / 5
    midfield = (
        (squad["CM1"]["rating"] if squad["CM1"] else 0) +
        (squad["CM2"]["rating"] if squad["CM2"] else 0) +
        (squad["AM"]["rating"] if squad["AM"] else 0)
    ) / 3
    return round((defense_line * 0.7) + (midfield * 0.3), 1)

# Generates simple fixtures for the user team against all AI teams
def generate_schedule(user_team):
    fixtures_list = []
    for opponent in TEAMS.keys():
        if opponent != user_team:
            # Alternates home and away randomly
            if random.choice([True, False]):
                fixtures_list.append((user_team, opponent))
            else:
                fixtures_list.append((opponent, user_team))
    random.shuffle(fixtures_list)
    return fixtures_list

# Initialize league table with all teams including user team and sets all team stats to 0
def create_league_table(user_team):
    table = []
    all_team_names = list(TEAMS.keys()) + [user_team]
    for name in all_team_names:
        table.append({
            "team": name, "played": 0, "wins": 0, "draws": 0, "losses": 0, "points": 0, "gd": 0
        })
    return table

# Simulates match outcome between user's team and opposition team by calculating factors such as
# expected goals for each team, expected goal scorers, and probability of positions in team to
# score or not.
def simulate_match(user_attack, user_defense, opp_attack, opp_defense, user_scorers, opp_scorers):
    def expected_goals(attack, defense):
        base = (attack - defense) / 20
        return max(0.2, 1.2 + base)

    user_xg = expected_goals(user_attack, opp_defense)
    opp_xg = expected_goals(opp_attack, user_defense)

    user_goals = min(6, max(0, int(random.gauss(user_xg, 1))))
    opp_goals = min(6, max(0, int(random.gauss(opp_xg, 1))))

    # Positional Scoring Weights
    # user_scorers list structure order is: [ST, (LW, RW), AM, (CM1, CM2), (LB, CB1, CB2, RB), GK] 
    user_positional_weights = [
        60,
        35, 35,
        20,
        10, 10,
        3, 3, 3, 3,
        0.1   
    ]

    user_match_scorers = []
    if user_goals > 0 and user_scorers:
        # Match weights exactly to how many players are actually in the pool
        current_weights = user_positional_weights[:len(user_scorers)]
        # Python uses weights to pick players with custom probability
        user_match_scorers = random.choices(user_scorers, weights=current_weights, k=user_goals)

    # Simple random fallback for AI teams since they use flat text lists in teams.py
    opp_match_scorers = []
    for _ in range(opp_goals):
        if opp_scorers:
            opp_match_scorers.append(random.choice(opp_scorers))

    return user_goals, opp_goals, user_match_scorers, opp_match_scorers

# Simulates random outcomes for teams outside of user team vs opposition team
def simulate_ai_league(table, user_team, opponent):
    # Goal margins 1 through 5
    margins = [1, 2, 3, 4, 5]
    # Highest probability for 1, lowest for 5
    margin_weights = [50, 30, 12, 6, 2] 

    # Updates team stats for all other teams
    for club in table:
        if club["team"] != user_team and club["team"] != opponent:
            outcome = random.choice(["win", "draw", "loss"])
            club["played"] += 1
            
            if outcome == "win":
                club["wins"] += 1
                club["points"] += 3
                # Randomly choose a positive GD based on weights
                club["gd"] += random.choices(margins, weights=margin_weights, k=1)[0]
            elif outcome == "draw":
                club["draws"] += 1
                club["points"] += 1
                # Draws result in +0 GD change
                club["gd"] += 0 
            else:
                club["losses"] += 1
                # Randomly choose a negative GD based on weights
                club["gd"] -= random.choices(margins, weights=margin_weights, k=1)[0]



# --- Routes ---

# Route: Team Setup: handles displaying the home page where users choose their team name.
# POST request saves the team name into the user session and redirects to the transfer market
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        session["team_name"] = request.form["team_name"]
        return redirect(url_for("transfer_market"))
    return render_template("home.html")

# Route: Transfer Market Dashboard: hub for managing the team roster, filtering players by position,
# and sorting by rating. Automatically detects if a season just finished to wipe old schedule data
# and re-open editing
@app.route("/transfer-market")
def transfer_market():
    team_name = session.get("team_name", "My Team")

    # Clear out remnants of previous match logic if returning from career end
    if session.get("current_week", 0) >= len(session.get("schedule", [])) and len(session.get("schedule", [])) > 0:
        # Reset career tracking counters so the app knows we are in 'edit squad' mode now
        session["current_week"] = 0
        session["schedule"] = []
        # Force reload players list with fresh attributes
        session["available_players"] = get_players()

    if "selected_player" not in session:
        session["selected_player"] = None

    if "squad" not in session:
        session["squad"] = {pos: None for pos in ["ST", "LW", "RW", "AM", "CM1", "CM2", "LB", "CB1", "CB2", "RB", "GK"]}

    # Read locally to keep the session cookie light
    all_market_players = get_players()

    # Sets budget amount
    if "budget" not in session:
        session["budget"] = 700

    # 1. Get the filters from the URL query parameters
    selected_position = request.args.get("position", "All")
    selected_sort = request.args.get("sort", "high_low")  # Defaults to High -> Low

    # 2. Determine rating sort modifier based on user selection
    # If high_low, a 90 rating becomes -90 (comes first). If low_high, 90 stays 90 (comes last).
    rating_modifier = -1 if selected_sort == "high_low" else 1

    # 3. Sort the players using both rules
    players = sorted(
        all_market_players,
        key=lambda x: (
            # Rule 1: Position Priority (0 matches come first, 1 unmatched comes second)
            0 if selected_position == "All" or selected_position in x.get("positions", []) else 1,
            # Rule 2: Rating direction determined by the modifier
            x["rating"] * rating_modifier
        )
    )

    squad_players = [p["name"] for p in session["squad"].values() if p]
    team_complete = all(player is not None for player in session["squad"].values())

    return render_template(
        "transfer_market.html",
        players=players,
        team_name=team_name,
        get_price=get_price,
        budget=session["budget"],
        squad_players=squad_players,
        team_complete=team_complete,
        selected_position=selected_position,
        selected_sort=selected_sort  # Pass this back to keep the dropdown synchronized
    )

# Route: Initiate Player Purchase: Searches for a chosen player from the market database, checks if the user has
# enough budget, and flags them as the 'selected_player' in the session to prepare them for positional assignment
@app.route("/buy/<player_name>", methods=["POST"])
def buy_player(player_name):
    position_filter = request.args.get("position", "All")
    sort_filter = request.args.get("sort", "high_low")

    # Read locally instead of saving to session
    all_market_players = get_players()
    for player in all_market_players:
        price = get_price(player["rating"])
        if player["name"] == player_name:
            if session["budget"] < price:
                # Forward filters even on failed budget checks
                return redirect(url_for("transfer_market", position=position_filter, sort=sort_filter))
            session["selected_player"] = player
            break

    session.modified = True
    
    # 2. Forward the filters back to the transfer market route
    return redirect(url_for("transfer_market", position=position_filter, sort=sort_filter))

# Route: Complete Player Assignment: Takes the active 'selected_player' and locks them into a specific formation
# slot (e.g., ST, GK). Deducts the funds from the budget and refunds money if a player was already occupying that slot
@app.route("/assign/<position>", methods=["POST"])
def assign_position(position):
    player = session.get("selected_player")
    if not player:
        return redirect(url_for("transfer_market"))

    # Capture the filters to prevent resets
    position_filter = request.args.get("position", "All")
    sort_filter = request.args.get("sort", "high_low")

    old_player = session["squad"].get(position)
    if old_player:
        session["budget"] += get_price(old_player["rating"])

    session["squad"][position] = {
        "name": player["name"],
        "rating": player["rating"]
    }
    
    session["budget"] -= get_price(player["rating"])
    session["selected_player"] = None
    session.modified = True

    return redirect(url_for("transfer_market", position=position_filter, sort=sort_filter))

# Route: Sell Roster Player: Removes a player from the team's squad array, recalculates their transfer value,
# and adds those funds back into the user's available budget
@app.route("/sell/<player_name>", methods=["POST"])
def sell_player(player_name):
    position_filter = request.args.get("position", "All")
    sort_filter = request.args.get("sort", "high_low")

    squad = session["squad"]
    for position in squad:
        if squad[position] and squad[position]["name"] == player_name:
            session["budget"] += get_price(squad[position]["rating"])
            squad[position] = None
            break
    session["squad"] = squad
    session.modified = True
    return redirect(url_for("transfer_market", position=position_filter, sort=sort_filter))

# Route: Release All Players: Wipes the active formation entirely, clears every position, and returns 100%
# of the squad's value back to the budget
@app.route("/clear-squad", methods=["POST"])
def clear_squad():
    position_filter = request.args.get("position", "All")
    sort_filter = request.args.get("sort", "high_low")

    squad = session["squad"]
    for position in squad:
        if squad[position]:
            session["budget"] += get_price(squad[position]["rating"])
            squad[position] = None
    session["squad"] = squad
    session.modified = True
    return redirect(url_for("transfer_market", position=position_filter, sort=sort_filter))

# Route: Career Setup: Verifies a valid team is built, generates a 38-game schedule balancing
# home and away pairings, computes the custom team offensive/defensive ratings, initializes league stats, and
# resets tracking counters
@app.route("/start-career", methods=["POST"])
def start_career():
    team_name = session.get("team_name")
    squad = session.get("squad")

    if not team_name or not squad or any(player is None for player in squad.values()):
        return redirect(url_for("transfer_market"))
    
    try:
        # 38-WEEK LOGIC
        first_half = []
        for opponent in TEAMS.keys():
            if opponent != team_name:
                if random.choice([True, False]):
                    first_half.append((team_name, opponent))
                else:
                    first_half.append((opponent, team_name))
        random.shuffle(first_half)

        # Reverse the matches for the second half (swapping home/away)
        second_half = [(away, home) for (home, away) in first_half]
        
        # Combine them to get exactly 38 games
        session["schedule"] = first_half + second_half

        session["team_attack"] = calculate_attack(squad)
        session["team_defense"] = calculate_defense(squad)

        all_teams = TEAMS.copy()
        all_teams[team_name] = {
            "attack": session["team_attack"],
            "defense": session["team_defense"],
            "scorers": [squad[p]["name"] for p in ["ST", "LW", "RW", "AM", "CM1", "CM2", "LB", "CB1", "CB2", "RB", "GK"] if squad.get(p)]
        }
        session["all_teams"] = all_teams
        session["league_table"] = create_league_table(team_name)

        session.update({
            "wins": 0, "draws": 0, "losses": 0, "match_results": [], "last_match": None, "current_week": 0, "goal_counts": {}
        })

        session.pop("selected_player", None)
        session.modified = True

        return redirect(url_for("career"))

    except Exception as e:
        return f"App crashed during career generation: {e}", 500

# Route: Career dashboard: Renders the current status of the season, sorting the current league standings,
# resolving goalscorer stats (with tie-breaker handling), and showing upcoming fixtures.
@app.route("/career")
def career():
    schedule = session.get("schedule", [])
    current_week = session.get("current_week", 0)

    if not schedule:
        return redirect(url_for("transfer_market"))

    if current_week >= len(schedule):
        user_match = ("Season Over", "Season Over")
    else:
        user_match = schedule[current_week]

    # Sorts by points descending (-x["points"]), then by team name ascending (x["team"])
    table = sorted(
        session.get("league_table", []), 
        key=lambda x: (-x["points"], -x["gd"], x["team"])
    )

    # CALCULATE CURRENT TOP SCORER (WITH TIES)
    goal_counts = session.get("goal_counts", {})
    if goal_counts:
        # 1. Find the highest number of goals scored by anyone
        max_goals = max(goal_counts.values())
        
        # 2. Collect ALL players who have scored that maximum amount
        top_scorers = [f"{name} ({goals} Goals)" for name, goals in goal_counts.items() if goals == max_goals]
        
        # 3. Join them together with a comma or slash
        top_scorer_text = ", ".join(top_scorers)
    else:
        top_scorer_text = "None yet"

    return render_template(
        "career.html",
        attack=session.get("team_attack"),
        defense=session.get("team_defense"),
        wins=session.get("wins", 0),
        draws=session.get("draws", 0),
        losses=session.get("losses", 0),
        top_scorer_text=top_scorer_text,
        results=session.get("match_results", []),
        league_table=table,
        fixtures=[user_match],
        last_match=session.get("last_match"),
        current_week=current_week,
        user_match=user_match,
        len_schedule=len(schedule)
    )

# Route: Process Match Simulation: Simulates the active week's match by feeding ratings into the physics/math generator.
# Updates points, records, user score logs, tracks scorer metrics, and prompts AI vs AI league outcomes before saving
@app.route("/next-week", methods=["POST"])
def next_week():
    current = session.get("current_week", 0)
    schedule = session.get("schedule", [])

    if current >= len(schedule):
        return redirect(url_for("career"))

    user_team = session["team_name"]
    user_attack = session["team_attack"]
    user_defense = session["team_defense"]

    home, away = schedule[current]
    opponent = away if home == user_team else home

    all_teams = session.get("all_teams", TEAMS)
    opp_stats = all_teams.get(opponent, {"attack": 75, "defense": 75, "scorers": ["Unknown"]})

    user_scorer_pool = all_teams[user_team]["scorers"]
    opp_scorer_pool = opp_stats["scorers"]

    # Run game sim
    user_goals, opp_goals, user_match_scorers, opp_match_scorers = simulate_match(
        user_attack, user_defense,
        opp_stats["attack"], opp_stats["defense"],
        user_scorer_pool, opp_scorer_pool
    )

    # Map the goals and scorers dynamically to who is playing Home vs Away
    home_goals = user_goals if home == user_team else opp_goals
    away_goals = opp_goals if home == user_team else user_goals
    home_scorers = user_match_scorers if home == user_team else opp_match_scorers
    away_scorers = opp_match_scorers if home == user_team else user_match_scorers

    # Update league table records for both teams
    table = session["league_table"]
    for club in table:
        if club["team"] == opponent:
            club["played"] += 1
            # Add exact goal difference for the opponent (their goals minus user goals)
            club["gd"] += (opp_goals - user_goals)
            if opp_goals > user_goals:
                club["wins"] += 1; club["points"] += 3
            elif opp_goals == user_goals:
                club["draws"] += 1; club["points"] += 1
            else:
                club["losses"] += 1

        elif club["team"] == user_team:
            club["played"] += 1
            # Add exact goal difference for the user (user goals minus opponent goals)
            club["gd"] += (user_goals - opp_goals)
            if user_goals > opp_goals:
                club["wins"] += 1; club["points"] += 3; session["wins"] += 1
            elif user_goals == opp_goals:
                club["draws"] += 1; club["points"] += 1; session["draws"] += 1
            else:
                club["losses"] += 1; session["losses"] += 1
            
            # TRACK GOALS SAFELY IN SESSION
            goal_counts = dict(session.get("goal_counts", {}))
            for scorer in user_match_scorers:
                goal_counts[scorer] = goal_counts.get(scorer, 0) + 1
            session["goal_counts"] = goal_counts

    # Keep a running list text log
    result_str = f"Week {current+1}: {home} {home_goals} - {away_goals} {away}"
    match_results = session.get("match_results", [])
    match_results.append(result_str)
    session["match_results"] = match_results

    # Save detailed structured data including lists of goalscorers
    session["last_match"] = {
        "home": home,
        "away": away,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "home_scorers": home_scorers,  
        "away_scorers": away_scorers   
    }

    simulate_ai_league(table, user_team, opponent)

    session["league_table"] = table
    session["current_week"] = current + 1
    session.modified = True

    return redirect(url_for("career"))

# Route: Reset State: Destroys all active data cookies stored within the session framework and maps back to home
@app.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)