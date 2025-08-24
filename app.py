# app.py
import streamlit as st
import google.generativeai as genai
import time
import ast
from datetime import datetime, timedelta
from users import check_login, create_user_page, get_mongo_client, register_user, login_user

# Import agentic intelligence features (optional - won't break if file doesn't exist)
try:
    from agentic_intelligence import get_quick_insight, get_proactive_notification
    AGENTIC_FEATURES_AVAILABLE = True
except ImportError:
    AGENTIC_FEATURES_AVAILABLE = False

# Import fitness agent features (optional - won't break if file doesn't exist)
try:
    from fitness_agent import get_fitness_insight, get_activity_recommendation
    FITNESS_AGENT_AVAILABLE = True
except ImportError:
    FITNESS_AGENT_AVAILABLE = False

# ======================================================================================
# API Configuration and Database Setup
# ======================================================================================

# Configure the Gemini API. The key is retrieved from Streamlit's secrets.
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except KeyError:
    st.error("Gemini API key not found. Please add 'GEMINI_API_KEY' to your `.streamlit/secrets.toml` file.")
    st.stop()

def save_to_db(data):
    """Saves a single food choice to the MongoDB database."""
    client = get_mongo_client()
    db = client["food_agent_db"]
    collection = db["food_choices"]
    collection.insert_one(data)

def fetch_history_from_db(user_id):
    """Fetches all food choices for a specific user from the database."""
    client = get_mongo_client()
    db = client["food_agent_db"]
    collection = db["food_choices"]
    return list(collection.find({"user_id": user_id}).sort("timestamp", -1))


# ======================================================================================
# Predefined Food Choices & Categories
# ======================================================================================

# User-defined eating occasions/categories
CATEGORIES = [
    "Daily choices",
    "Protein is calling",
    "Period is killing",
    "Desserts",
    "Cheat meals",
    "Exams",
    "Favourites"
]

# Predefined food items for each category
FOOD_CHOICES = {
    "Daily choices": {
        "Indian": ["Bajra Roti with Dal Palak", "Makai Roti with Chhole Masala", "Jowar Roti with Rajma Masala", "Indian-style Tomato Soup", "Spinach and Garlic Gravy", "Jowar Roti with Baingan Bharta (no chunks)", "Bajra Roti with Mixed Vegetable Gravy"],
        "South Indian": ["Idli Sambar", "Dosa with Coconut Chutney", "Uttapam with Onion and Capsicum", "Tomato Onion Curry", "Lemon Rice with Sambar Gravy", "Rasam Rice with Fried Potatoes (no whole vegetables)", "Plain Dosa with Onion-Capsicum Curry"]
    },
    "Protein is calling": ["Tofu Palak Gravy", "Soya Rice with Masala", "Paneer Butter Masala", "Chhole Bhature", "Rajma Chawal", "Lentil Soup with spices", "Grilled Tofu with a creamy dip", "Paneer Tikka Masala without skewers"],
    "Period is killing": ["Chocolate Ice Cream", "Spicy Noodles", "Cheese Pizza", "French Fries with Dip", "Warm Soup with Garlic Bread", "Mac & Cheese", "Hot Chocolate"],
    "Desserts": ["Gulab Jamun", "Kulfi", "Chocolate Brownie", "Fruit Salad with Ice Cream", "Ras Malai"],
    "Cheat meals": ["Veg Burger with Fries", "Loaded Nachos with Cheese", "Veggie Pizza with extra toppings", "Manchurian Gravy with Hakka Noodles", "Veg Fried Rice"],
    "Exams": ["Khichdi", "Curd Rice with pickle", "Simple Dal Roti", "Vegetable Soup", "Pav Bhaji (easy version)"]
}

# ======================================================================================
# Helper Functions
# ======================================================================================

def generate_new_choices(category, current_choices, user_context="for me"):
    """
    Calls the Gemini API to generate more creative food choices for a given category.
    The prompt is adjusted based on the user context.
    """
    if user_context == "for me":
        # Prompt for Diya's preferences
        prompt = f"""
        You are a creative food expert. Based on the category '{category}', suggest three new and delicious food items for a picky vegetarian eater who does not eat eggs.
        The user's preferences are:
        - Only eats gravies and soups, not whole vegetables (except for onion, capsicum, garlic etc).
        - Prefers Jowar, Bajra, and Makai rotis.
        - For 'Daily choices', focus on Indian and South Indian meals.
        - For 'Protein is calling', suggest dishes with tofu, paneer, chhole, or rajma.
        - For 'Period is killing', suggest comfort foods.
        - For 'Exams', suggest easy and quick comfort meals.
        - The current list of choices is: {', '.join(current_choices)}.
        Your response should be a clean, concise JSON array of strings, with exactly three new food names. Do not include any other text, just the JSON.
        Example: ["Dish 1", "Dish 2", "Dish 3"]
        """
    else:
        # Generic prompt for the other user
        prompt = f"""
        You are a creative food expert. Based on the category '{category}', suggest three new and delicious food items for a person who is interested in exploring their palate.
        The current list of choices is: {', '.join(current_choices)}.
        Your response should be a clean, concise JSON array of strings, with exactly three new food names. Do not include any other text, just the JSON.
        Example: ["Dish 1", "Dish 2", "Dish 3"]
        """

    try:
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        response = model.generate_content(prompt)
        
        if response and response.text:
            try:
                raw_text = response.text.strip('`').replace('json', '').strip()
                new_choices = ast.literal_eval(raw_text)
                if isinstance(new_choices, list) and len(new_choices) == 3:
                    return new_choices
                else:
                    st.warning("Generated response was not a valid list of three items.")
                    return None
            except (ValueError, SyntaxError):
                st.warning("Could not parse the generated choices.")
                return None
    except Exception as e:
        st.error(f"An error occurred while generating new choices: {e}")
        return None
    return None

def main_app():
    """Main application logic for logged-in users."""
    st.set_page_config(
        page_title="My AI Food Agent",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Session state for app mode
    if 'app_mode' not in st.session_state:
        st.session_state.app_mode = "Diya's Moods"

    # --- Sidebar ---
    with st.sidebar:
        st.header(f"Logged in as: {st.session_state.current_user}")
        st.markdown("---")
        
        # User mode selection
        app_mode = st.radio(
            "Who are you using the app for?",
            ["Diya's Moods", "My Personal Choices"],
            index=0 if st.session_state.app_mode == "Diya's Moods" else 1
        )
        st.session_state.app_mode = app_mode
        
        target_user_id = "Diya" if st.session_state.app_mode == "Diya's Moods" else st.session_state.current_user
        
        st.markdown("---")

        # Period Tracker - Expandable Container
        with st.expander("📅 Period Tracker", expanded=False):
            st.markdown("Your agent will use this to proactively suggest meals when your cravings might begin.")
            
            client = get_mongo_client()
            db = client["food_agent_db"]
            period_tracker_collection = db["period_tracker"]
            tracker_data = period_tracker_collection.find_one({"user_id": "Diya"})

            if tracker_data:
                last_period_date_value = tracker_data.get('last_period_date')
                if isinstance(last_period_date_value, datetime):
                    last_period_date_value = last_period_date_value.date()
                else:
                    last_period_date_value = datetime.now().date() - timedelta(days=28)
                cycle_length_value = tracker_data.get('cycle_length', 28)
            else:
                last_period_date_value = datetime.now().date() - timedelta(days=28)
                cycle_length_value = 28

            last_period_date = st.date_input("Last Period Start Date", value=last_period_date_value)
            cycle_length = st.number_input("Average Cycle Length (days)", min_value=1, value=cycle_length_value, key="cycle_length_input")

            if st.button("Save Tracker Data", use_container_width=True, key="save_tracker_button"):
                data_to_save = {
                    "user_id": "Diya",
                    "last_period_date": datetime.combine(last_period_date, datetime.min.time()),
                    "cycle_length": cycle_length
                }
                period_tracker_collection.update_one(
                    {"user_id": "Diya"},
                    {"$set": data_to_save},
                    upsert=True
                )
                st.success("Period tracker data saved successfully!")
                st.rerun()

            today = datetime.now().date()
            next_period_start = last_period_date + timedelta(days=cycle_length)
            
            st.markdown("---")
            st.markdown("**Your Agent's Predictions:**")
            
            predicted_dates = [next_period_start + timedelta(days=i * cycle_length) for i in range(5)]
            for i, date in enumerate(predicted_dates):
                st.markdown(f"**{i+1}.** {date.strftime('%B %d, %Y')}")
                
            st.markdown("---")
            
            days_since_last_period = (today - last_period_date).days
            days_to_next_period = cycle_length - days_since_last_period

            if days_to_next_period <= 2 and days_to_next_period > 0:
                st.warning("Hey Diya, your agent knows your period is around the corner. It's okay to feel a bit moody! We've got you covered.")
                if st.button("Get a 'Period is killing' suggestion now!", use_container_width=True, key="proactive_suggestion_button"):
                    st.session_state.proactive_prediction_trigger = True
                    st.session_state.prediction_category = "Period is killing"
                    st.rerun()

            elif days_to_next_period <= cycle_length and days_to_next_period >= cycle_length - 4: # Assuming a 5-day period
                st.info("Hey Diya, we know you're on your period, so we have some personalized suggestions to help with the cravings!")
                if st.button("Get a 'Period is killing' suggestion now!", use_container_width=True, key="proactive_suggestion_button"):
                    st.session_state.proactive_prediction_trigger = True
                    st.session_state.prediction_category = "Period is killing"
                    st.rerun()
        
        # Fitness Agent - Expandable Container
        if FITNESS_AGENT_AVAILABLE:
            with st.expander("🏃‍♀️ Fitness Agent", expanded=False):
                st.markdown("Your fitness agent connects to Samsung S Health to provide personalized meal recommendations based on your activity.")
                
                # Get fitness insight
                fitness_insight = get_fitness_insight(target_user_id, get_mongo_client())
                st.info(fitness_insight)
                
                # Get activity-based recommendation
                activity_recommendation = get_activity_recommendation(target_user_id, get_mongo_client())
                if activity_recommendation:
                    st.markdown("---")
                    st.markdown("**Today's Activity-Based Suggestion:**")
                    st.markdown(f"🎯 **{activity_recommendation['type']}**: {activity_recommendation['message']}")
                    
                    if activity_recommendation.get("category"):
                        if st.button(f"Get {activity_recommendation['category']} suggestions", 
                                   key=f"fitness_{activity_recommendation['type']}"):
                            st.session_state.auto_category = activity_recommendation['category']
                            st.rerun()
                
                st.markdown("---")
                st.markdown("**Quick Actions:**")
                
                # Manual activity input (for testing/backup)
                st.markdown("**Manual Activity Input (for testing):**")
                activity_type = st.selectbox(
                    "Activity Level Today:",
                    ["Low Activity", "Moderate Activity", "High Activity", "Workout Day"],
                    key="manual_activity_input"
                )
                
                if st.button("Get Activity-Based Suggestion", use_container_width=True, key="manual_activity_button"):
                    st.session_state.manual_activity_trigger = True
                    st.session_state.manual_activity_type = activity_type
                    st.rerun()
                
                # S Health connection status
                st.markdown("---")
                st.markdown("**S Health Connection:**")
                if st.button("🔗 Connect to S Health", use_container_width=True, key="connect_shealth_button"):
                    st.info("S Health integration coming soon! For now, use manual input above.")
                
                # Fitness Dashboard
                st.markdown("---")
                st.markdown("**Fitness Dashboard:**")
                if st.button("📊 Open Fitness Dashboard", use_container_width=True, key="open_fitness_dashboard_button"):
                    st.session_state.show_fitness_dashboard = True
                    st.rerun()
        
        # Meal Planner Agent - Expandable Container
        with st.expander("🍽️ Meal Planner Agent", expanded=False):
            st.markdown("Let your agent plan your meals for a few days, based on your cravings and history.")
            
            if 'meal_plan' not in st.session_state:
                num_days = st.number_input("How many days to plan?", min_value=1, max_value=7, value=3, key="num_days_input_sidebar")
                meal_plan_category = st.selectbox(
                    "Focus category:",
                    CATEGORIES[:-1],
                    key="meal_plan_category_input_sidebar"
                )
                
                if st.button("Generate Meal Plan", use_container_width=True, key="generate_plan_button_sidebar"):
                    with st.spinner("Your agent is creating your meal plan..."):
                        history = fetch_history_from_db(target_user_id)
                        category_history = [item for item in history if item['category'] == meal_plan_category]
                        
                        recent_history_str = "\n".join([
                            f"Food: {item['food']}, Rating: {item['rating']}/10, Comments: {item.get('comments', 'None')}"
                            for item in category_history[:5]
                        ])

                        if st.session_state.app_mode == "Diya's Moods":
                            plan_prompt = f"""
                            You are a food expert creating a meal plan for a picky vegetarian eater who does not eat eggs. The user wants to plan meals for the next {num_days} days, focusing on the "{meal_plan_category}" category.
                            
                            The user's general preferences are:
                            - Only eats gravies and soups, not whole vegetables (except for onion, capsicum, garlic etc).
                            - Prefers Jowar, Bajra, and Makai rotis.
                            - Is on a weightloss journey but not that hardcore.
                            - For 'Daily choices', focus on Indian and South Indian meals.
                            - For 'Protein is calling', suggest dishes with tofu, paneer, chhole, or rajma.
                            - For 'Period is killing', suggest comfort foods.
                            - For 'Exams', suggest easy and quick comfort meals.
                            
                            Here are some of their past choices and comments for this specific category:
                            {recent_history_str if recent_history_str else "No specific comments for this category yet."}
                            
                            Please create a unique meal plan for each of the {num_days} days. Each plan should include a suggested dish and a brief reason why they might like it, mixing insights from their general preferences and their specific comments.
                            
                            The response must be a clean, concise JSON array of objects. Each object should have a 'day', 'dish', and 'reason' key.
                            
                            Example response:
                            [
                              {{"day": "Day 1", "dish": "Dish 1", "reason": "Reason 1"}},
                              {{"day": "Day 2", "dish": "Dish 2", "reason": "Reason 2"}},
                              {{"day": "Day 3", "dish": "Dish 3", "reason": "Reason 3"}}
                            ]
                            """
                        else:
                            plan_prompt = f"""
                            You are a food expert creating a meal plan for a person who wants to explore new food choices. The user wants to plan meals for the next {num_days} days, focusing on the "{meal_plan_category}" category.
                            
                            Here are some of their past choices and comments for this specific category:
                            {recent_history_str if recent_history_str else "No specific comments for this category yet."}
                            
                            Please create a unique meal plan for each of the {num_days} days. Each plan should include a suggested dish and a brief reason why they might like it, referencing their past comments.
                            
                            The response must be a clean, concise JSON array of objects. Each object should have a 'day', 'dish', and 'reason' key.
                            
                            Example response:
                            [
                              {{"day": "Day 1", "dish": "Dish 1", "reason": "Reason 1"}},
                              {{"day": "Day 2", "dish": "Dish 2", "reason": "Reason 2"}},
                              {{"day": "Day 3", "dish": "Dish 3", "reason": "Reason 3"}}
                            ]
                            """

                        try:
                            model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
                            response = model.generate_content(plan_prompt)
                            
                            if response and response.text:
                                raw_text = response.text.strip('`').replace('json', '').strip()
                                meal_plan = ast.literal_eval(raw_text)
                                if isinstance(meal_plan, list) and len(meal_plan) == num_days:
                                    st.session_state['meal_plan'] = meal_plan
                                    st.session_state['meal_plan_category'] = meal_plan_category
                                    st.session_state['meal_plan_days'] = num_days
                                else:
                                    st.error("The AI agent provided an invalid response format.")
                            else:
                                st.error("Sorry, your agent couldn't create a meal plan right now.")
                        except Exception as e:
                            st.error(f"An error occurred while creating the meal plan: {e}")
                    
                    st.rerun()
            
            # Display and rate the generated meal plan within the sidebar container
            if 'meal_plan' in st.session_state and st.session_state.meal_plan:
                st.markdown("---")
                st.markdown("**Generated Meal Plan:**")
                
                meal_feedback = []
                for i, item in enumerate(st.session_state.meal_plan):
                    st.markdown(f"**{item['day']}:** {item['dish']}")
                    st.caption(f"Reason: {item['reason']}")
                    
                    # Individual rating for each meal
                    rating = st.select_slider(
                        f"Rate '{item['dish']}' (1-10):",
                        options=range(1, 11),
                        value=5,
                        key=f"plan_rating_{i}_sidebar"
                    )
                    comments = st.text_area(
                        f"Comments for '{item['dish']}' (optional):",
                        placeholder="e.g., The flavor was good, but it was too spicy.",
                        key=f"plan_comments_input_{i}_sidebar"
                    )
                    
                    meal_feedback.append({
                        "dish": item['dish'],
                        "category": st.session_state.meal_plan_category,
                        "rating": rating,
                        "comments": comments,
                        "reason": item['reason']
                    })
                    
                    st.markdown("---")
                
                if st.button("Save Plan", key="save_meal_plan_button_sidebar"):
                    with st.spinner("Saving meal plan..."):
                        for feedback in meal_feedback:
                            data_to_save = {
                                "user_id": target_user_id,
                                "category": feedback['category'],
                                "food": feedback['dish'],
                                "rating": feedback['rating'],
                                "comments": f"Meal plan suggestion: {feedback['dish']} | {feedback['comments']}",
                                "timestamp": time.time()
                            }
                            save_to_db(data_to_save)
                    st.success("Meal plan saved to history!")
                    del st.session_state.meal_plan
                    del st.session_state.meal_plan_category
                    del st.session_state.meal_plan_days
                    st.rerun()

        # Logout button at the bottom of sidebar
        # Agentic Intelligence Features - Expandable Container
        if AGENTIC_FEATURES_AVAILABLE:
            with st.expander("🤖 Your AI Food Agent", expanded=False):
                st.markdown("Your agent is learning your patterns and making smart suggestions!")
                
                # Get a quick insight
                insight = get_quick_insight(target_user_id, get_mongo_client())
                st.info(insight)
                
                # Get proactive notification if any
                notification = get_proactive_notification(target_user_id, get_mongo_client())
                if notification:
                    priority_color = {
                        "high": "🔴",
                        "medium": "🟡", 
                        "low": "🟢"
                    }.get(notification["priority"], "⚪")
                    
                    st.markdown(f"{priority_color} **{notification['type'].title()}**: {notification['message']}")
                    
                    if notification.get("category"):
                        if st.button(f"Get {notification['category']} suggestions", 
                                   key=f"notification_{notification['type']}"):
                            st.session_state.auto_category = notification['category']
                            st.rerun()
                
                st.markdown("---")
                st.markdown("**Quick Actions:**")
                
                # Quick access to agentic dashboard
                if st.button("📊 View Full Dashboard", use_container_width=True, key="view_dashboard_sidebar"):
                    st.session_state.show_agentic_dashboard = True
                    st.rerun()
                
                # Quick pattern check
                if st.button("🔍 Check My Patterns", use_container_width=True, key="check_patterns_sidebar"):
                    st.session_state.quick_pattern_check = True
                    st.rerun()
        
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True, key="logout_button"):
            st.session_state.is_authenticated = False
            st.session_state.current_user = None
            st.rerun()


    # --- Main Content Area ---
    st.title(f"🍽️ Welcome, {st.session_state.current_user}!")
    if st.session_state.app_mode == "Diya's Moods":
        st.markdown("Diya's personal palate assistant, built to learn Diyas picky eating habits:")
    else:
        st.markdown("Your personal palate assistant, built to learn your picky eating habits:")
    st.markdown("---")

    # Handle proactive prediction trigger, auto-category suggestions, and manual activity triggers
    if ('proactive_prediction_trigger' in st.session_state and st.session_state.proactive_prediction_trigger) or \
       ('auto_category' in st.session_state and st.session_state.auto_category) or \
       ('manual_activity_trigger' in st.session_state and st.session_state.manual_activity_trigger):
        
        # Debug: Show what's in session state
        if 'auto_category' in st.session_state:
            st.info(f"Debug: auto_category is set to: {st.session_state.auto_category}")
        
        # Determine which category to use and store activity data if needed
        activity_data = None
        manual_activity_type = None
        if 'auto_category' in st.session_state:
            prediction_category = st.session_state.auto_category
            del st.session_state.auto_category  # Clear it after use
        elif 'manual_activity_trigger' in st.session_state and st.session_state.manual_activity_trigger:
            # Handle manual activity trigger
            manual_activity_type = st.session_state.get('manual_activity_type', 'Moderate Activity')
            from fitness_agent import analyze_activity_data
            activity_data = analyze_activity_data(manual_activity_type)
            prediction_category = activity_data['category']
        else:
            prediction_category = "Period is killing"
        
        with st.spinner("Your agent is thinking..."):
            # Use the current target_user_id (could be Diya or the logged-in user)
            history = fetch_history_from_db(target_user_id)
            
            # Show activity-based message if it's a manual activity trigger
            if activity_data and manual_activity_type:
                st.info(f"🏃‍♀️ **{manual_activity_type}**: {activity_data['message']}")
                st.info(f"🎯 **Nutrition Focus**: {activity_data['nutrition_focus']}")
            
            category_history = [item for item in history if item['category'] == prediction_category]
            
            recent_category_history_str = "\n".join([
                f"Food: {item['food']}, Rating: {item['rating']}/10, Comments: {item.get('comments', 'None')}" 
                for item in category_history[:5]
            ])
            
            # Adjust preferences based on user mode
            if st.session_state.app_mode == "Diya's Moods":
                general_preferences = [
                    "- Only eats gravies and soups, not whole vegetables (except for onion, capsicum, garlic etc).",
                    "- Prefers Jowar, Bajra, and Makai rotis.",
                    "- For 'Daily choices', focus on Indian and South Indian meals.",
                    "- For 'Protein is calling', suggest dishes with tofu, paneer, chhole, or rajma.",
                    "- For 'Period is killing', suggest comfort foods.",
                    "- For 'Exams', suggest easy and quick comfort meals.",
                    "- For 'Desserts' and 'Cheat meals', be creative with the given options."
                ]
            else:
                general_preferences = [
                    "- User is exploring new food choices and preferences.",
                    "- Focus on variety and discovery.",
                    "- Consider past ratings and comments for personalization."
                ]
            
            prompt = f"""
            You are a food expert assisting a user with their food choices. The user's current eating occasion is "{prediction_category}".
            
            The user's general preferences are:
            {chr(10).join(general_preferences)}
            
            Here are some of their past choices and comments for this specific category:
            {recent_category_history_str if recent_category_history_str else "No specific comments for this category yet."}
            
            Please suggest exactly three new and delicious food items the user might enjoy for this occasion. For each dish, provide a brief, personalized reason why they might like it, mixing insights from their general preferences and their specific comments.
            
            The response must be a clean, concise JSON array of objects, with each object having a 'dish' and a 'reason' key. Do not include any other text, just the JSON.
            
            Example response:
            [
              {{"dish": "Dish 1", "reason": "Reason 1"}},
              {{"dish": "Dish 2", "reason": "Reason 2"}},
              {{"dish": "Dish 3", "reason": "Reason 3"}}
            ]
            """
            
            try:
                model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
                response = model.generate_content(prompt)
                
                if response and response.text:
                    raw_text = response.text.strip('`').replace('json', '').strip()
                    predicted_choices_with_reasons = ast.literal_eval(raw_text)
                    if isinstance(predicted_choices_with_reasons, list) and len(predicted_choices_with_reasons) == 3:
                        st.session_state['predicted_choices_with_reasons'] = predicted_choices_with_reasons
                        st.session_state['predicted_category'] = prediction_category
                    else:
                        st.error("The AI agent provided an invalid response format.")
                else:
                    st.error("Sorry, your agent couldn't come up with a prediction right now.")
            except Exception as e:
                st.error(f"An error occurred while getting the prediction: {e}")
        
        if 'proactive_prediction_trigger' in st.session_state:
            del st.session_state.proactive_prediction_trigger
        if 'manual_activity_trigger' in st.session_state:
            del st.session_state.manual_activity_trigger
            del st.session_state.manual_activity_type
        st.rerun()





    # ---
    st.divider()

    # Agentic Intelligence Dashboard (conditional display)
    if AGENTIC_FEATURES_AVAILABLE and st.session_state.get('show_agentic_dashboard', False):
        st.divider()
        st.header("🤖 Your AI Food Agent Dashboard")
        st.markdown("Your agent is learning your patterns and making smart suggestions!")
        
        # Import and initialize the agent
        from agentic_intelligence import initialize_agentic_features, display_agentic_dashboard
        
        agent = initialize_agentic_features(target_user_id, get_mongo_client())
        display_agentic_dashboard(agent)
        
        # Add a close button
        if st.button("❌ Close Dashboard", key="close_dashboard"):
            del st.session_state.show_agentic_dashboard
            st.rerun()
        
        st.divider()
    
    # Fitness Dashboard (conditional display)
    if FITNESS_AGENT_AVAILABLE and st.session_state.get('show_fitness_dashboard', False):
        st.divider()
        st.header("🏃‍♀️ Fitness Dashboard")
        st.markdown("Track your fitness goals, calculate BMI, and get calorie-based meal suggestions!")
        
        # Import fitness agent functions
        from fitness_agent import (
            calculate_bmi, calculate_daily_calories, get_calorie_based_meal_suggestion,
            save_fitness_goals, get_fitness_goals
        )
        
        # Get existing fitness goals
        existing_goals = get_fitness_goals(target_user_id, get_mongo_client())
        
        # Fitness Goals and BMI Calculator
        with st.container(border=True):
            st.subheader("🎯 Fitness Goals & BMI Calculator")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Personal Information:**")
                weight_kg = st.number_input("Weight (kg)", min_value=30.0, max_value=200.0, value=float(existing_goals.get('weight_kg', 60.0)) if existing_goals else 60.0, step=0.1)
                height_cm = st.number_input("Height (cm)", min_value=100.0, max_value=200.0, value=float(existing_goals.get('height_cm', 160.0)) if existing_goals else 160.0, step=0.1)
                age = st.number_input("Age", min_value=13, max_value=100, value=int(existing_goals.get('age', 25)) if existing_goals else 25)
                gender = st.selectbox("Gender", ["female", "male"], index=0 if (existing_goals and existing_goals.get('gender', 'female') == 'female') else 1)
                
                st.markdown("**Activity Level:**")
                # Get activity level index safely
                activity_levels = ["sedentary", "light", "moderate", "active", "very_active"]
                default_activity_index = 2  # moderate
                if existing_goals and 'activity_level' in existing_goals:
                    try:
                        activity_index = activity_levels.index(existing_goals['activity_level'])
                    except ValueError:
                        activity_index = default_activity_index
                else:
                    activity_index = default_activity_index
                
                activity_level = st.selectbox(
                    "Daily Activity Level",
                    activity_levels,
                    index=activity_index,
                    format_func=lambda x: {
                        "sedentary": "Sedentary (Little/no exercise)",
                        "light": "Light (1-3 days/week)",
                        "moderate": "Moderate (3-5 days/week)",
                        "active": "Active (6-7 days/week)",
                        "very_active": "Very Active (Hard exercise, physical job)"
                    }[x]
                )
                
                st.markdown("**Fitness Goal:**")
                # Get goal index safely
                goals = ["maintain", "lose", "gain"]
                default_goal_index = 0  # maintain
                if existing_goals and 'goal' in existing_goals:
                    try:
                        goal_index = goals.index(existing_goals['goal'])
                    except ValueError:
                        goal_index = default_goal_index
                else:
                    goal_index = default_goal_index
                
                goal = st.selectbox(
                    "Primary Goal",
                    goals,
                    index=goal_index,
                    format_func=lambda x: {
                        "maintain": "Maintain Current Weight",
                        "lose": "Lose Weight",
                        "gain": "Gain Weight"
                    }[x]
                )
            
            with col2:
                st.markdown("**BMI & Health Insights:**")
                if st.button("Calculate BMI & Calories", use_container_width=True, key="calculate_bmi_button"):
                    # Calculate BMI
                    bmi_data = calculate_bmi(weight_kg, height_cm)
                    
                    # Calculate daily calories
                    calorie_data = calculate_daily_calories(weight_kg, height_cm, age, gender, activity_level, goal)
                    
                    # Save to session state for display
                    st.session_state.bmi_data = bmi_data
                    st.session_state.calorie_data = calorie_data
                    
                    # Save fitness goals
                    goals_data = {
                        'weight_kg': weight_kg,
                        'height_cm': height_cm,
                        'age': age,
                        'gender': gender,
                        'activity_level': activity_level,
                        'goal': goal
                    }
                    if save_fitness_goals(target_user_id, get_mongo_client(), goals_data):
                        st.success("Fitness goals saved successfully!")
                    
                    st.rerun()
                
                # Display BMI results
                if 'bmi_data' in st.session_state:
                    bmi_data = st.session_state.bmi_data
                    st.metric("BMI", f"{bmi_data['bmi']}", bmi_data['category'])
                    st.info(f"**Health Insight:** {bmi_data['health_insight']}")
                    st.info(f"**Meal Focus:** {bmi_data['meal_focus']}")
                
                # Display calorie results
                if 'calorie_data' in st.session_state:
                    calorie_data = st.session_state.calorie_data
                    st.metric("Daily Target Calories", f"{calorie_data['target_calories']}", calorie_data['goal_message'])
                    
                    st.markdown("**Macro Breakdown:**")
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Protein", f"{calorie_data['macros']['protein_g']}g")
                    with col_b:
                        st.metric("Carbs", f"{calorie_data['macros']['carbs_g']}g")
                    with col_c:
                        st.metric("Fat", f"{calorie_data['macros']['fat_g']}g")
        
        # Calorie-Based Meal Suggestions
        if 'calorie_data' in st.session_state:
            st.divider()
            st.subheader("🍽️ Calorie-Based Meal Suggestions")
            
            # Show learning insights
            from fitness_agent import get_fitness_meal_insights
            insights_data = get_fitness_meal_insights(target_user_id, get_mongo_client())
            
            if insights_data['total_meals_rated'] > 0:
                st.info("🧠 **Your Agent's Learning Progress:**")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Meals Rated", insights_data['total_meals_rated'])
                with col_b:
                    st.metric("Avg Rating", f"{insights_data['avg_rating']}/10")
                with col_c:
                    st.metric("Calorie Preference", insights_data['calorie_preferences'].title())
                
                st.info("💡 **Insights:**")
                for insight in insights_data['insights']:
                    st.write(f"• {insight}")
                
                st.info("🎯 **Recommendations:**")
                for rec in insights_data['recommendations']:
                    st.write(f"• {rec}")
            else:
                st.info("🧠 **Your agent is ready to learn!** Start rating meals to get personalized insights.")
            
            meal_type = st.selectbox(
                "Select Meal Type:",
                ["breakfast", "lunch", "dinner", "snack"],
                format_func=lambda x: x.title()
            )
            
            if st.button("Get Meal Suggestions", use_container_width=True, key="get_calorie_meals_button"):
                with st.spinner("Generating personalized meal suggestions..."):
                    target_calories = st.session_state.calorie_data['target_calories']
                    meal_suggestions = get_calorie_based_meal_suggestion(
                        target_user_id, get_mongo_client(), target_calories, meal_type
                    )
                    st.session_state.meal_suggestions = meal_suggestions
                    st.session_state.last_meal_type = meal_type  # Track last meal type
                    st.rerun()
            
            # Display meal suggestions with rating functionality
            if 'meal_suggestions' in st.session_state:
                # Clear rating saved flag if it exists
                if 'rating_saved' in st.session_state:
                    del st.session_state.rating_saved
                
                meal_suggestions = st.session_state.meal_suggestions
                st.info(meal_suggestions['message'])
                st.info(f"**Target Range:** {meal_suggestions['target_range']}")
                
                # Show learning insight
                if 'learning_insight' in meal_suggestions:
                    st.info(f"🧠 **Agent Learning:** {meal_suggestions['learning_insight']}")
                
                # Check if suggestions are personalized
                if any('personalization' in suggestion for suggestion in meal_suggestions['suggestions']):
                    st.success("🎯 **Personalized Suggestions:** These meals are tailored to your preferences based on your ratings!")
                else:
                    st.info("📋 **Default Suggestions:** Rate these meals to help your agent learn your preferences!")
                
                for i, suggestion in enumerate(meal_suggestions['suggestions']):
                    with st.expander(f"🍽️ {suggestion['dish']} ({suggestion['estimated_cals']} calories)"):
                        st.markdown(f"**Nutrition Focus:** {suggestion['focus']}")
                        st.markdown(f"**Estimated Calories:** {suggestion['estimated_cals']}")
                        
                        # Show personalization if available
                        if 'personalization' in suggestion:
                            st.info(f"🎯 **Personalized:** {suggestion['personalization']}")
                        
                        # Rating section for each meal
                        st.markdown("---")
                        st.markdown("**Rate this suggestion to help your agent learn:**")
                        
                        rating = st.select_slider(
                            f"Rate '{suggestion['dish']}' (1-10):",
                            options=range(1, 11),
                            value=5,
                            key=f"fitness_meal_rating_{i}"
                        )
                        
                        comments = st.text_area(
                            f"Comments on '{suggestion['dish']}' (optional):",
                            placeholder="e.g., Loved the protein content, perfect portion size",
                            key=f"fitness_meal_comments_{i}"
                        )
                        
                        if st.button(f"Save Rating for {suggestion['dish']}", key=f"save_fitness_rating_{i}"):
                            from fitness_agent import save_fitness_meal_rating
                            
                            # Prepare meal data for saving
                            meal_data = {
                                'dish': suggestion['dish'],
                                'meal_type': meal_type,
                                'estimated_cals': suggestion['estimated_cals'],
                                'rating': rating,
                                'comments': comments,
                                'focus': suggestion['focus'],
                                'target_calories': st.session_state.calorie_data['target_calories']
                            }
                            
                            if save_fitness_meal_rating(target_user_id, get_mongo_client(), meal_data):
                                st.success(f"Rating saved! Your agent is learning from your feedback. Refresh to get new suggestions!")
                                # Clear the rating saved flag
                                st.session_state.rating_saved = True
                            else:
                                st.error("Failed to save rating. Please try again.")
                
                st.info(f"💡 **Nutrition Tip:** {meal_suggestions['nutrition_tip']}")
                
                # Show rating system info
                if 'rating_saved' in st.session_state:
                    st.success("✅ **Rating System Active:** Your agent is learning from your feedback! Each rating helps improve future suggestions.")
                
                # Add button to refresh insights after rating
                if st.button("🔄 Refresh Learning Insights", key="refresh_insights_button"):
                    st.rerun()
        
        # Add a close button
        if st.button("❌ Close Fitness Dashboard", key="close_fitness_dashboard"):
            del st.session_state.show_fitness_dashboard
            if 'bmi_data' in st.session_state:
                del st.session_state.bmi_data
            if 'calorie_data' in st.session_state:
                del st.session_state.calorie_data
            if 'meal_suggestions' in st.session_state:
                del st.session_state.meal_suggestions
            st.rerun()
        
        st.divider()
    
    # Quick Pattern Check (conditional display)
    if AGENTIC_FEATURES_AVAILABLE and st.session_state.get('quick_pattern_check', False):
        st.divider()
        st.header("🔍 Your Food Patterns")
        
        # Import and initialize the agent for quick check
        from agentic_intelligence import initialize_agentic_features
        
        agent = initialize_agentic_features(target_user_id, get_mongo_client())
        user_data = agent.get_user_patterns()
        
        if user_data["patterns"]:
            st.subheader("💡 Quick Insights")
            for insight in user_data["insights"][:3]:  # Show only first 3 insights
                st.info(insight)
            
            # Show category preferences
            if user_data["patterns"].get("category_preferences"):
                st.subheader("📊 Category Preferences")
                for category, data in user_data["patterns"]["category_preferences"].items():
                    if data["count"] >= 2:  # Only show categories with enough data
                        avg_rating = data["avg_rating"]
                        count = data["count"]
                        st.metric(
                            label=category,
                            value=f"{avg_rating:.1f}/10",
                            delta=f"{count} choices"
                        )
        else:
            st.info("Your agent needs more data to learn your patterns. Start rating your food choices!")
        
        # Add a close button
        if st.button("❌ Close Pattern Check", key="close_pattern_check"):
            del st.session_state.quick_pattern_check
            st.rerun()
        
        st.divider()

    st.header("Log a New Food Choice")
    st.markdown(f"Select an eating occasion and rate the food you chose to help train your agent. You can now enter your own dishes too!")

    with st.container(border=True):
        if 'selected_category' not in st.session_state:
            st.session_state.selected_category = CATEGORIES[0]
        if 'chosen_food' not in st.session_state:
            st.session_state.chosen_food = ""
        if 'auto_fill' not in st.session_state:
            st.session_state.auto_fill = False
        
        selected_category = st.selectbox(
            "Choose an Eating Occasion",
            CATEGORIES,
            index=CATEGORIES.index(st.session_state.selected_category) if st.session_state.selected_category in CATEGORIES else 0,
            key="log_category",
            help="Select the category that best describes your current meal."
        )
        
        if selected_category != st.session_state.selected_category:
            st.session_state.selected_category = selected_category
            st.session_state.chosen_food = ""
            st.session_state.auto_fill = False

        chosen_food = ""
        if selected_category == "Favourites":
            chosen_food = st.text_input(
                "Enter your favourite food:",
                value=st.session_state.chosen_food if st.session_state.auto_fill else "",
                placeholder="e.g., Spicy Jalapeno Pasta",
                key="fav_food_input"
            )
        else:
            category_choices = []
            if selected_category in FOOD_CHOICES:
                if selected_category == "Daily choices":
                    for cuisine, meals in FOOD_CHOICES[selected_category].items():
                        category_choices.extend([f"{meal} ({cuisine})" for meal in meals])
                else:
                    category_choices = FOOD_CHOICES[selected_category]

            choices_with_custom = ["-- Select or Enter a Dish --"] + category_choices + ["-- Enter my own --"]
            
            initial_index = 0
            if st.session_state.auto_fill and st.session_state.chosen_food:
                for i, choice in enumerate(choices_with_custom):
                    if choice == st.session_state.chosen_food or (choice != "-- Select or Enter a Dish --" and choice != "-- Enter my own --" and st.session_state.chosen_food in choice):
                        initial_index = i
                        break
                if initial_index == 0:
                    initial_index = len(choices_with_custom) - 1
            
            chosen_food_option = st.selectbox(
                "Select the food you chose",
                choices_with_custom,
                index=initial_index,
                key="food_option_select",
                help="Choose from the curated list or enter a new one."
            )

            if chosen_food_option == "-- Enter my own --":
                chosen_food = st.text_input(
                    "Enter your dish here:",
                    value=st.session_state.chosen_food if st.session_state.auto_fill else "",
                    placeholder="e.g., Creamy Mushroom Soup",
                    key="custom_food_input"
                )
            else:
                chosen_food = chosen_food_option.split(' (')[0] if chosen_food_option and chosen_food_option != "-- Select or Enter a Dish --" else ""
        
        if st.session_state.auto_fill:
            st.session_state.auto_fill = False

        rating = st.select_slider(
            "Rate your choice (1 = Dislike, 10 = Love)",
            options=range(1, 11),
            value=5,
            key="food_rating"
        )
        
        comments = st.text_area(
            "Your comments on this dish (optional):",
            placeholder="e.g., The paneer was super soft and the gravy was creamy.",
            key="food_comments_input"
        )


        if st.button("Save Choice", use_container_width=True, key="save_button"):
            if chosen_food and chosen_food != "-- Select or Enter a Dish --":
                data_to_save = {
                    "user_id": target_user_id,
                    "category": selected_category,
                    "food": chosen_food,
                    "rating": rating,
                    "comments": comments,
                    "timestamp": time.time()
                }
                save_to_db(data_to_save)
                st.success(f"Saved: '{chosen_food}' with a rating of {rating}/10 for {target_user_id}.")
            else:
                st.warning("Please select or enter a food item.")

    # ---
    st.divider()

    st.header("Ask Your Agent for a Prediction")
    st.markdown("Let your agent suggest a food item based on your current eating occasion.")

    with st.container(border=True):
        prediction_category = st.selectbox(
            "My Current Eating Occasion",
            CATEGORIES[:-1],
            key="predict_category",
            help="Select your current need, and your agent will suggest something for you."
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Get a Personalized Suggestion", use_container_width=True, key="get_prediction_button"):
                with st.spinner("Your agent is thinking..."):
                    history = fetch_history_from_db(target_user_id)
                    
                    category_history = [item for item in history if item['category'] == prediction_category]
                    
                    recent_category_history_str = "\n".join([
                        f"Food: {item['food']}, Rating: {item['rating']}/10, Comments: {item.get('comments', 'None')}" 
                        for item in category_history[:5]
                    ])

                    if st.session_state.app_mode == "Diya's Moods":
                        prompt = f"""
                        You are a food expert assisting a picky vegetarian eater who does not eat eggs. The user's current eating occasion is "{prediction_category}".
                        
                        The user's general preferences are:
                        - Only eats gravies and soups, not whole vegetables (except for onion, capsicum, garlic etc).
                        - Prefers Jowar, Bajra, and Makai rotis.
                        - For 'Daily choices', focus on Indian and South Indian meals.
                        - For 'Protein is calling', suggest dishes with tofu, paneer, chhole, or rajma.
                        - For 'Period is killing', suggest comfort foods.
                        - For 'Exams', suggest easy and quick comfort meals.
                        - For 'Desserts' and 'Cheat meals', be creative with the given options.
                        
                        
                        Here are some of their past choices and comments for this specific category:
                        {recent_category_history_str if recent_category_history_str else "No specific comments for this category yet."}
                        
                        Please suggest exactly three new and delicious food items the user might enjoy for this occasion. For each dish, provide a brief, personalized reason why they might like it, mixing insights from their general preferences and their specific comments.
                        
                        The response must be a clean, concise JSON array of objects, with each object having a 'dish' and a 'reason' key. Do not include any other text, just the JSON.
                        
                        Example response:
                        [
                          {{"dish": "Dish 1", "reason": "Reason 1"}},
                          {{"dish": "Dish 2", "reason": "Reason 2"}},
                          {{"dish": "Dish 3", "reason": "Reason 3"}}
                        ]
                        """
                    else:
                        prompt = f"""
                        You are a food expert assisting a person who wants to explore new food choices. The user's current eating occasion is "{prediction_category}".
                        
                        Here are some of their past choices and comments for this specific category:
                        {recent_category_history_str if recent_category_history_str else "No specific comments for this category yet."}
                        
                        Please suggest exactly three new and delicious food items the user might enjoy for this occasion. For each dish, provide a brief, personalized reason why they might like it, referencing their past comments.
                        
                        The response must be a clean, concise JSON array of objects, with each object having a 'dish' and a 'reason' key. Do not include any other text, just the JSON.
                        
                        Example response:
                        [
                          {{"dish": "Dish 1", "reason": "Reason 1"}},
                          {{"dish": "Dish 2", "reason": "Reason 2"}},
                          {{"dish": "Dish 3", "reason": "Reason 3"}}
                        ]
                        """
                    
                    try:
                        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
                        response = model.generate_content(prompt)
                        
                        if response and response.text:
                            raw_text = response.text.strip('`').replace('json', '').strip()
                            predicted_choices_with_reasons = ast.literal_eval(raw_text)
                            if isinstance(predicted_choices_with_reasons, list) and len(predicted_choices_with_reasons) == 3:
                                st.session_state['predicted_choices_with_reasons'] = predicted_choices_with_reasons
                                st.session_state['predicted_category'] = prediction_category
                            else:
                                st.error("The AI agent provided an invalid response format.")
                        else:
                            st.error("Sorry, your agent couldn't come up with a prediction right now.")
                    except Exception as e:
                        st.error(f"An error occurred while getting the prediction: {e}")
                
                st.rerun()

        with col2:
            if st.button("Generate More Choices", use_container_width=True, key="generate_choices_button"):
                with st.spinner("Generating new ideas..."):
                    current_choices = []
                    if prediction_category in FOOD_CHOICES:
                        if prediction_category == "Daily choices":
                            for meals in FOOD_CHOICES[prediction_category].values():
                                current_choices.extend(meals)
                        else:
                            current_choices = FOOD_CHOICES[prediction_category]
                    
                    new_choices = generate_new_choices(prediction_category, current_choices, user_context="for me" if st.session_state.app_mode == "Diya's Moods" else "for myself")
                    if new_choices:
                        st.session_state['generated_choices'] = new_choices
                        st.session_state['generated_category'] = prediction_category
                        st.rerun()

    if 'predicted_choices_with_reasons' in st.session_state and st.session_state.predicted_choices_with_reasons:
        st.divider()
        st.subheader("Your AI Agent's Suggestions")
        st.markdown(f"Today's suggestions for your **{st.session_state.predicted_category}** craving:")
        
        with st.container(border=True):
            if 'show_predicted_rating' not in st.session_state:
                st.session_state.show_predicted_rating = False
            
            for i, item in enumerate(st.session_state.predicted_choices_with_reasons):
                st.markdown(f"**{item['dish']}**")
                st.caption(f"Reason: {item['reason']}")
                if st.button(f"I'd like to rate '{item['dish']}'", key=f"rate_predicted_{i}"):
                    st.session_state['show_predicted_rating'] = True
                    st.session_state['food_to_rate'] = item['dish']
                    st.session_state['category_to_rate'] = st.session_state.predicted_category
                    st.rerun()
            
            if st.session_state.show_predicted_rating and st.session_state.food_to_rate:
                st.divider()
                st.write(f"**Rating:** {st.session_state.food_to_rate}")
                predicted_rating = st.select_slider(
                    "Rate your choice (1 = Dislike, 10 = Love)",
                    options=range(1, 11),
                    value=5,
                    key="predicted_rating_slider"
                )
                
                predicted_comments = st.text_area(
                    "Your comments on this dish (optional):",
                    placeholder="e.g., The paneer was super soft and the gravy was creamy.",
                    key="predicted_food_comments_input"
                )

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Save Suggestion", key="save_predicted"):
                        data_to_save = {
                            "user_id": target_user_id,
                            "category": st.session_state.category_to_rate,
                            "food": st.session_state.food_to_rate,
                            "rating": predicted_rating,
                            "comments": predicted_comments,
                            "timestamp": time.time()
                        }
                        save_to_db(data_to_save)
                        st.success(f"Saved: '{st.session_state.food_to_rate}' with a rating of {predicted_rating}/10.")
                        
                        st.session_state.predicted_choices_with_reasons = [
                            item for item in st.session_state.predicted_choices_with_reasons if item['dish'] != st.session_state.food_to_rate
                        ]

                        if not st.session_state.predicted_choices_with_reasons:
                            del st.session_state.predicted_choices_with_reasons
                            del st.session_state.predicted_category
                        
                        st.session_state.show_predicted_rating = False
                        st.session_state.food_to_rate = None
                        st.session_state.category_to_rate = None
                        st.rerun()
                
                with col2:
                    if st.button("Cancel Rating", key="cancel_predicted"):
                        st.session_state.show_predicted_rating = False
                        st.session_state.food_to_rate = None
                        st.session_state.category_to_rate = None
                        st.rerun()

            if st.button("Clear All Suggestions", key="clear_all_predictions"):
                del st.session_state.predicted_choices_with_reasons
                del st.session_state.predicted_category
                if 'show_predicted_rating' in st.session_state:
                    del st.session_state.show_predicted_rating
                if 'food_to_rate' in st.session_state:
                    del st.session_state.food_to_rate
                if 'category_to_rate' in st.session_state:
                    del st.session_state.category_to_rate
                st.rerun()


    if 'generated_choices' in st.session_state and st.session_state.generated_choices:
        st.divider()
        st.subheader("Generated Choices")
        st.info(f"Here are some new ideas for the '{st.session_state.generated_category}' category:")

        with st.container(border=True):
            generated_food = st.selectbox(
                "Select a generated choice to rate and save:",
                st.session_state.generated_choices,
                key="generated_food_select"
            )
            
            generated_rating = st.select_slider(
                "Rate your choice (1 = Dislike, 10 = Love)",
                options=range(1, 11),
                value=5,
                key="generated_rating"
            )
            
            generated_comments = st.text_area(
                "Your comments on this dish (optional):",
                placeholder="e.g., The paneer was super soft and the gravy was creamy.",
                key="generated_food_comments_input"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save Generated Choice", key="save_generated"):
                    data_to_save = {
                        "user_id": target_user_id,
                        "category": st.session_state.generated_category,
                        "food": generated_food,
                        "rating": generated_rating,
                        "comments": generated_comments,
                        "timestamp": time.time()
                    }
                    save_to_db(data_to_save)
                    st.success(f"Saved: '{generated_food}' with a rating of {generated_rating}/10 for {target_user_id}.")
                    
                    st.session_state.generated_choices.remove(generated_food)

                    if not st.session_state.generated_choices:
                        del st.session_state.generated_choices
                        del st.session_state.generated_category
                    st.rerun()
            
            with col2:
                if st.button("Cancel", key="cancel_generated"):
                    del st.session_state.generated_choices
                    del st.session_state.generated_category
                    st.rerun()

    # ---
    st.divider()

    st.header("Your Food Choice History")
    st.markdown("Review your past choices to identify patterns.")

    if 'history_page' not in st.session_state:
        st.session_state.history_page = 1
    
    history_per_page = 5
    
    full_history = fetch_history_from_db(target_user_id)
    total_items = len(full_history)
    
    if total_items > 0:
        end_index = st.session_state.history_page * history_per_page
        start_index = end_index - history_per_page
        
        history_to_display = full_history[start_index:end_index]

        for item in history_to_display:
            with st.expander(f"{item['food']} (Rated: {item['rating']}/10)"):
                st.write(f"**Eating Occasion:** {item['category']}")
                st.write(f"**Rating:** {item['rating']}/10")
                if item.get('comments'):
                    st.write(f"**Comments:** {item['comments']}")
                st.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item['timestamp']))}")
        
        if end_index < total_items:
            if st.button("Show More History", use_container_width=True):
                st.session_state.history_page += 1
                st.rerun()
        else:
            st.info("You have reached the end of your food history.")
    else:
        st.info("No food choices logged yet. Start adding some above!")

# --- Application Entry Point ---
if __name__ == "__main__":
    if not check_login():
        create_user_page()
    else:
        main_app()
