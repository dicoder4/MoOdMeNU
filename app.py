# app.py
import streamlit as st
import google.generativeai as genai
import time
import ast
from datetime import datetime, timedelta
from users import check_login, create_user_page, get_mongo_client, register_user, login_user

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
        
        with st.expander("Period Tracker & Insights", expanded=True):
            with st.container(border=True):
                # Proactive messaging section
                st.header("Agent's Proactive Insights")
                today = datetime.now().date()
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
                    
                    days_since_last_period = (today - last_period_date_value).days
                    days_to_next_period = cycle_length_value - days_since_last_period

                    if days_to_next_period <= 2 and days_to_next_period > 0:
                        st.warning("Hey Diya, your agent knows your period is around the corner. It's okay to feel a bit moody! We've got you covered.")
                    elif days_to_next_period <= cycle_length_value and days_to_next_period >= cycle_length_value - 4: # Assuming a 5-day period
                        st.info("Hey Diya, we know you're on your period, so we have some personalized suggestions to help with the cravings!")
                        if st.button("Get a 'Period is killing' suggestion now!", use_container_width=True):
                            st.session_state.proactive_prediction_trigger = True
                            st.session_state.last_period_date = today
                            st.rerun()

                st.markdown("---")

                st.header("Period Tracker")
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
                cycle_length = st.number_input("Average Cycle Length (days)", min_value=1, value=cycle_length_value)

                if st.button("Save Tracker Data", use_container_width=True):
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
                
                st.markdown("---")
                st.markdown("**Next Predicted Period Dates:**")
                
                predicted_dates = [last_period_date + timedelta(days=i * cycle_length) for i in range(1, 6)]
                for i, date in enumerate(predicted_dates):
                    st.markdown(f"**{i+1}.** {date.strftime('%B %d, %Y')}")
                    
                st.markdown("---")
        # Logout button always visible in sidebar
        if st.button("Logout", use_container_width=True):
            st.session_state.is_authenticated = False
            st.session_state.current_user = None
            st.rerun()

    # --- Main Content Area ---
    st.title(f"🍽️ Welcome, {st.session_state.current_user}!")
    if st.session_state.app_mode == "Diya's Moods":
        st.markdown("Diya's personal palate assistant, built to learn Diyas picky eating habits:")
    else:
        st.markdown("Your personal palate assistant, built to learn your picky eating habits:")

    # Handle proactive prediction trigger
    if 'proactive_prediction_trigger' in st.session_state and st.session_state.proactive_prediction_trigger:
        with st.spinner("Your agent is thinking..."):
            history = fetch_history_from_db("Diya")
            prediction_category = "Period is killing"
            
            category_history = [item for item in history if item['category'] == prediction_category]
            
            recent_category_history_str = "\n".join([
                f"Food: {item['food']}, Rating: {item['rating']}/10, Comments: {item.get('comments', 'None')}" 
                for item in category_history[:5]
            ])
            
            general_preferences = [
                "- Only eats gravies and soups, not whole vegetables (except for onion, capsicum, garlic etc).",
                "- Prefers Jowar, Bajra, and Makai rotis.",
                "- For 'Daily choices', focus on Indian and South Indian meals.",
                "- For 'Protein is calling', suggest dishes with tofu, paneer, chhole, or rajma.",
                "- For 'Period is killing', suggest comfort foods.",
                "- For 'Exams', suggest easy and quick comfort meals.",
                "- For 'Desserts' and 'Cheat meals', be creative with the given options."
            ]
            
            prompt = f"""
            You are a food expert assisting a picky vegetarian eater who does not eat eggs. The user's current eating occasion is "{prediction_category}".
            
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
        
        del st.session_state.proactive_prediction_trigger
        st.rerun()


    # ---
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
