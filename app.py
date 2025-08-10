# app.py
import streamlit as st
import google.generativeai as genai
import time
import ast
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

def generate_new_choices(category, current_choices):
    """
    Calls the Gemini API to generate more creative food choices for a given category.
    """
    prompt = f"""
    You are a creative food expert. Based on the category '{category}', suggest three new and delicious food items for a picky vegetarian eater who does not eat eggs.
    The user is trying to expand their palate. The user's preferences are:
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
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        response = model.generate_content(prompt)
        
        # Parse the JSON response
        if response and response.text:
            try:
                # The model may wrap the JSON in markdown code fences
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
    st.title(f"🍽️ Welcome, {st.session_state.current_user}!")
    st.markdown("Diya's personal palate assistant, built to learn Diyas picky eating habits:')")

    # ---
    st.divider()

    # Log a New Food Choice Section
    st.header("Log a New Food Choice")
    st.markdown("Select an eating occasion and rate the food you chose to help train your agent. You can now enter your own dishes too!")

    with st.container(border=True):
        selected_category = st.selectbox(
            "Choose an Eating Occasion",
            CATEGORIES,
            index=0,
            help="Select the category that best describes your current meal."
        )

        chosen_food = ""
        if selected_category == "Favourites":
            chosen_food = st.text_input(
                "Enter your favourite food:",
                placeholder="e.g., Spicy Jalapeno Pasta"
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
            
            chosen_food_option = st.selectbox(
                "Select the food you chose",
                choices_with_custom,
                help="Choose from the curated list or enter a new one."
            )

            if chosen_food_option == "-- Enter my own --":
                chosen_food = st.text_input(
                    "Enter your dish here:",
                    placeholder="e.g., Creamy Mushroom Soup"
                )
            else:
                chosen_food = chosen_food_option.split(' (')[0] if chosen_food_option and chosen_food_option != "-- Select or Enter a Dish --" else ""

        rating = st.select_slider(
            "Rate your choice (1 = Dislike, 10 = Love)",
            options=range(1, 11),
            value=5
        )

        if st.button("Save Choice", use_container_width=True):
            if chosen_food and chosen_food != "-- Select or Enter a Dish --":
                data_to_save = {
                    "user_id": st.session_state.current_user,
                    "category": selected_category,
                    "food": chosen_food,
                    "rating": rating,
                    "timestamp": time.time()
                }
                save_to_db(data_to_save)
                st.success(f"Saved: '{chosen_food}' with a rating of {rating}/10.")
            else:
                st.warning("Please select or enter a food item.")

    # ---
    st.divider()

    # AI Agent Prediction Section
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
            if st.button("Get a Prediction", use_container_width=True):
                with st.spinner("Your agent is thinking..."):
                    prompt_food_items = ""
                    if prediction_category in FOOD_CHOICES:
                        if prediction_category == "Daily choices":
                            all_meals = []
                            for meals in FOOD_CHOICES[prediction_category].values():
                                all_meals.extend(meals)
                            prompt_food_items = ", ".join(all_meals)
                        else:
                            prompt_food_items = ", ".join(FOOD_CHOICES[prediction_category])

                    prompt = f"""
                    I am a picky eater trying to discover my palate. Based on my current eating occasion, which is "{prediction_category}", please suggest one or two food items that I might enjoy. The available food choices for this category are: {prompt_food_items}.
                    I'm a vegetarian and do not eat eggs. For 'Daily choices', I only eat jowar, bajra, and makai rotis with gravies or soups (no whole vegetables, just onions, capsicum, garlic etc).
                    For 'Period is killing', suggest comfort foods that are easy to make.
                    For 'Exams', suggest easy and quick comfort meals.
                    For 'Protein is calling', suggest dishes with tofu, paneer, chhole, or rajma.
                    For 'Desserts' and 'Cheat meals', be creative with the given options.
                    Please be concise and friendly.
                    """
                    
                    try:
                        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
                        response = model.generate_content(prompt)
                        
                        if response and response.text:
                            st.success("Your agent suggests:")
                            st.write(response.text)
                        else:
                            st.error("Sorry, your agent couldn't come up with a prediction right now.")
                    except Exception as e:
                        st.error(f"An error occurred while getting the prediction: {e}")
        with col2:
            if st.button("Generate More Choices", use_container_width=True):
                with st.spinner("Generating new ideas..."):
                    current_choices = []
                    if prediction_category in FOOD_CHOICES:
                        if prediction_category == "Daily choices":
                            for meals in FOOD_CHOICES[prediction_category].values():
                                current_choices.extend(meals)
                        else:
                            current_choices = FOOD_CHOICES[prediction_category]
                    
                    new_choices = generate_new_choices(prediction_category, current_choices)
                    if new_choices:
                        st.success("Here are three new ideas:")
                        for choice in new_choices:
                            st.markdown(f"- **{choice}**")
                        st.info("You can copy these new suggestions and add them to your history.")


    # ---
    st.divider()

    # Food Choice History
    st.header("Your Food Choice History")
    st.markdown("Review your past choices to identify patterns.")

    history = fetch_history_from_db(st.session_state.current_user)

    if history:
        for item in history:
            with st.expander(f"{item['food']} (Rated: {item['rating']}/10)"):
                st.write(f"**Eating Occasion:** {item['category']}")
                st.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item['timestamp']))}")
    else:
        st.info("No food choices logged yet. Start adding some above!")

# --- Application Entry Point ---
if __name__ == "__main__":
    if not check_login():
        create_user_page()
    else:
        main_app()
