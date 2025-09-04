# fitness_agent.py
"""
Fitness Agent Module for MoOdMeNU

This module provides fitness-related insights and activity-based meal recommendations
by analyzing user activity data and communicating with the food agent.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import ast
import json
import google.generativeai as genai

def generate_gemini_fitness_suggestions(user_id: str, mongo_client, meal_type: str, cuisine_preference: str, min_cals: float, max_cals: float, food_choices_history: list) -> list:
    """
    Use Gemini to generate meal suggestions conditioned on cuisine, meal type, calorie band and user history.
    Returns a list of {dish, estimated_cals, focus} dicts.
    """
    # Build a concise, structured prompt for JSON output
    # Extract a short recent history snippet to ground the model
    recent_history_lines = []
    for item in food_choices_history[:8]:
        recent_history_lines.append(f"Dish: {item.get('food','')}, Rating: {item.get('rating',5)}/10, Category: {item.get('category','')}, Comments: {item.get('comments','')}")
    recent_history_text = "\n".join(recent_history_lines) if recent_history_lines else "None"

    cuisine_text = cuisine_preference if cuisine_preference and cuisine_preference != "Any" else "Any/Generic"

    prompt = f"""
    You are a nutrition-forward vegetarian meal planner. Generate diverse, non-repetitive meal ideas.

    Constraints:
    - Vegetarian only, no eggs. Prefer gravies/soups over whole vegetables when reasonable.
    - Meal type: {meal_type}
    - Cuisine focus: {cuisine_text}
    - Estimated calories MUST be within [{int(min_cals)}, {int(max_cals)}].
    - Consider the user's highly-rated items and avoid poorly-rated ones.
    - Keep names approachable for home cooking in India.

    User history (most recent first):
    {recent_history_text}

    Output EXACTLY a JSON array of 5 objects, no prose. Each object must be:
    {{
      "dish": "string, short name",
      "estimated_cals": number,  // integer calories in range
      "focus": "string, e.g., High protein | Balanced | Light | South Indian | North Indian"
    }}
    """

    try:
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        response = model.generate_content(prompt)
        if not response or not getattr(response, 'text', None):
            return []
        raw_text = response.text.strip('`').replace('json', '').strip()
        data = ast.literal_eval(raw_text)
        if not isinstance(data, list):
            return []
        cleaned = []
        for item in data:
            dish = str(item.get('dish', '')).strip()
            try:
                cals = int(round(float(item.get('estimated_cals', 0))))
            except Exception:
                cals = 0
            focus = str(item.get('focus', '')).strip() or 'Balanced'
            if not dish:
                continue
            # Enforce calorie bounds softly
            if cals < int(min_cals):
                cals = int(min_cals)
            if cals > int(max_cals):
                cals = int(max_cals)
            cleaned.append({
                'dish': dish,
                'estimated_cals': cals,
                'focus': focus,
                'meal_type': meal_type
            })
        return cleaned[:5]
    except Exception:
        return []

def get_fitness_insight(user_id: str, mongo_client) -> str:
    """
    Get a fitness insight based on the user's recent activity and food choices.
    
    Args:
        user_id: The user's ID
        mongo_client: MongoDB client connection
        
    Returns:
        A string containing the fitness insight
    """
    try:
        db = mongo_client["food_agent_db"]
        food_collection = db["food_choices"]
        
        # Get recent food choices to analyze patterns
        recent_food = list(food_collection.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(10))
        
        if not recent_food:
            return "Welcome! Your fitness agent is ready to help you make better food choices based on your activity."
        
        # Analyze recent food choices for fitness patterns
        high_protein_count = sum(1 for item in recent_food 
                               if any(keyword in item.get('food', '').lower() 
                                     for keyword in ['paneer', 'tofu', 'chhole', 'rajma', 'dal', 'protein']))
        
        comfort_food_count = sum(1 for item in recent_food 
                               if any(keyword in item.get('food', '').lower() 
                                     for keyword in ['ice cream', 'chocolate', 'pizza', 'fries', 'dessert']))
        
        if high_protein_count > comfort_food_count:
            return "Great job! You've been making protein-rich choices lately. Keep up the healthy eating!"
        elif comfort_food_count > high_protein_count:
            return "I notice you've been choosing comfort foods. Let's balance that with some nutritious options!"
        else:
            return "You're maintaining a good balance in your food choices. Keep listening to your body!"
            
    except Exception as e:
        return f"Your fitness agent is analyzing your patterns. Check back soon for personalized insights!"

def get_activity_recommendation(user_id: str, mongo_client) -> Optional[Dict[str, Any]]:
    """
    Get an activity-based meal recommendation.
    
    Args:
        user_id: The user's ID
        mongo_client: MongoDB client connection
        
    Returns:
        A dictionary containing the recommendation type, message, and suggested category
    """
    try:
        # For now, return a sample recommendation
        # In the future, this would connect to Samsung S Health API
        current_hour = datetime.now().hour
        
        # Morning recommendations
        if 6 <= current_hour < 12:
            return {
                "type": "Morning Energy",
                "message": "Start your day with a protein-rich breakfast to fuel your activities!",
                "category": "Protein is calling"
            }
        # Afternoon recommendations
        elif 12 <= current_hour < 17:
            return {
                "type": "Midday Fuel",
                "message": "Keep your energy up with a balanced meal that includes protein and carbs.",
                "category": "Daily choices"
            }
        # Evening recommendations
        elif 17 <= current_hour < 21:
            return {
                "type": "Evening Recovery",
                "message": "Time to refuel after your day's activities. Consider something comforting yet nutritious.",
                "category": "Protein is calling"
            }
        # Late night recommendations
        else:
            return {
                "type": "Late Night",
                "message": "If you're hungry, choose something light and easy to digest.",
                "category": "Daily choices"
            }
            
    except Exception as e:
        return None

def analyze_activity_data(activity_type: str) -> Dict[str, Any]:
    """
    Analyze manual activity input and provide recommendations.
    
    Args:
        activity_type: The type of activity (Low, Moderate, High, Workout)
        
    Returns:
        A dictionary with meal recommendations based on activity level
    """
    activity_recommendations = {
        "Low Activity": {
            "message": "On low activity days, focus on lighter meals to maintain energy balance.",
            "category": "Daily choices",
            "nutrition_focus": "Moderate portions, balanced nutrition"
        },
        "Moderate Activity": {
            "message": "Moderate activity calls for balanced meals with good protein and carbs.",
            "category": "Daily choices",
            "nutrition_focus": "Balanced protein, carbs, and healthy fats"
        },
        "High Activity": {
            "message": "High activity days need extra fuel! Focus on protein-rich meals for recovery.",
            "category": "Protein is calling",
            "nutrition_focus": "High protein, adequate carbs for energy"
        },
        "Workout Day": {
            "message": "Workout days require special attention to recovery nutrition. Protein is your friend!",
            "category": "Protein is calling",
            "nutrition_focus": "High protein, post-workout nutrition"
        }
    }
    
    return activity_recommendations.get(activity_type, {
        "message": "Choose a meal that makes you feel good and energized!",
        "category": "Daily choices",
        "nutrition_focus": "Balanced nutrition"
    })

def calculate_bmi(weight_kg: float, height_cm: float) -> Dict[str, Any]:
    """
    Calculate BMI and provide health insights.
    
    Args:
        weight_kg: Weight in kilograms
        height_cm: Height in centimeters
        
    Returns:
        Dictionary with BMI value, category, and health insights
    """
    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)
    
    if bmi < 18.5:
        category = "Underweight"
        health_insight = "You may need to increase your caloric intake with nutrient-dense foods."
        meal_focus = "High-calorie, nutrient-rich meals"
    elif 18.5 <= bmi < 25:
        category = "Normal weight"
        health_insight = "Great! You're in a healthy weight range. Focus on maintaining balanced nutrition."
        meal_focus = "Balanced, varied meals"
    elif 25 <= bmi < 30:
        category = "Overweight"
        health_insight = "Consider reducing caloric intake while maintaining nutrient density."
        meal_focus = "Lower-calorie, high-fiber meals"
    else:
        category = "Obese"
        health_insight = "Focus on gradual weight loss through balanced nutrition and portion control."
        meal_focus = "Portion-controlled, nutrient-dense meals"
    
    return {
        "bmi": round(bmi, 1),
        "category": category,
        "health_insight": health_insight,
        "meal_focus": meal_focus
    }

def calculate_daily_calories(weight_kg: float, height_cm: float, age: int, gender: str, activity_level: str, goal: str) -> Dict[str, Any]:
    """
    Calculate daily calorie needs based on various factors.
    
    Args:
        weight_kg: Weight in kilograms
        height_cm: Height in centimeters
        age: Age in years
        gender: "male" or "female"
        activity_level: "sedentary", "light", "moderate", "active", "very_active"
        goal: "maintain", "lose", "gain"
        
    Returns:
        Dictionary with calorie calculations and recommendations
    """
    # Calculate Basal Metabolic Rate (BMR) using Mifflin-St Jeor Equation
    if gender.lower() == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    
    # Activity multipliers
    activity_multipliers = {
        "sedentary": 1.2,      # Little or no exercise
        "light": 1.375,        # Light exercise 1-3 days/week
        "moderate": 1.55,      # Moderate exercise 3-5 days/week
        "active": 1.725,       # Hard exercise 6-7 days/week
        "very_active": 1.9     # Very hard exercise, physical job
    }
    
    # Calculate Total Daily Energy Expenditure (TDEE)
    tdee = bmr * activity_multipliers.get(activity_level.lower(), 1.55)
    
    # Adjust for goal
    if goal.lower() == "lose":
        target_calories = tdee - 500  # 500 calorie deficit for ~0.5kg/week loss
        goal_message = "Weight Loss: 500 calorie deficit for healthy weight loss"
    elif goal.lower() == "gain":
        target_calories = tdee + 300  # 300 calorie surplus for ~0.3kg/week gain
        goal_message = "Weight Gain: 300 calorie surplus for healthy weight gain"
    else:
        target_calories = tdee
        goal_message = "Weight Maintenance: Calories balanced for current weight"
    
    # Macro breakdown (simplified)
    protein_cals = target_calories * 0.25  # 25% protein
    carbs_cals = target_calories * 0.45    # 45% carbs
    fat_cals = target_calories * 0.30      # 30% fat
    
    return {
        "bmr": round(bmr),
        "tdee": round(tdee),
        "target_calories": round(target_calories),
        "goal_message": goal_message,
        "macros": {
            "protein_g": round(protein_cals / 4),
            "carbs_g": round(carbs_cals / 4),
            "fat_g": round(fat_cals / 9)
        }
    }

def get_calorie_based_meal_suggestion(user_id: str, mongo_client, target_calories: int, meal_type: str, cuisine_preference: str) -> Dict[str, Any]:
    """
    Get calorie-based meal suggestions based on user's food history and calorie goals.
    Now includes agentic learning from user ratings.
    
    Args:
        user_id: The user's ID
        mongo_client: MongoDB client connection
        target_calories: Target calories for the meal
        meal_type: "breakfast", "lunch", "dinner", "snack"
        cuisine_preference: The user's preferred cuisine type (e.g., "Indian", "Italian")
        
    Returns:
        Dictionary with meal suggestions and calorie information
    """
    try:
        db = mongo_client["food_agent_db"]
        food_collection = db["food_choices"]
        fitness_meals_collection = db["fitness_meals"]
        
        # Get user history and learning
        food_choices_history = list(food_collection.find({"user_id": user_id}).sort("timestamp", -1))
        fitness_meal_history = list(fitness_meals_collection.find({"user_id": user_id}).sort("timestamp", -1).limit(50))
        user_preferences = analyze_fitness_meal_preferences(fitness_meal_history)
        
        # Calorie ranges per meal type
        meal_calorie_ranges = {
            "breakfast": (target_calories * 0.25, target_calories * 0.35),
            "lunch": (target_calories * 0.3, target_calories * 0.4),
            "dinner": (target_calories * 0.25, target_calories * 0.35),
            "snack": (target_calories * 0.1, target_calories * 0.15)
        }
        min_cals, max_cals = meal_calorie_ranges.get(meal_type.lower(), (target_calories * 0.3, target_calories * 0.4))
        
        # Ask Gemini for candidates (no hardcoded menus)
        candidates = generate_gemini_fitness_suggestions(user_id, mongo_client, meal_type, cuisine_preference, min_cals, max_cals, food_choices_history)
        
        if not candidates:
            return {
                "message": f"I couldn't generate {cuisine_preference} {meal_type} options right now. Try again or adjust cuisine.",
                "target_range": f"{int(min_cals)}-{int(max_cals)} calories",
                "suggestions": [],
                "nutrition_tip": "Prefer whole foods, lean proteins, and complex carbs for sustained energy.",
                "learning_insight": user_preferences.get('insight', "Your agent is learning your preferences!")
            }
        
        # Filter/score against dislikes and history
        rated_dishes = {item.get('food', '').lower() for item in food_choices_history}
        disliked_dishes = {item.get('food', '').lower() for item in food_choices_history if item.get('rating', 0) <= 3}
        
        candidate_meals = [meal for meal in candidates if meal.get('dish', '').lower() not in disliked_dishes]
        
        scored_meals = []
        for meal in candidate_meals:
            # Ensure meal_type present for scoring
            meal['meal_type'] = meal_type
            score = calculate_meal_preference_score(meal, user_preferences, food_choices_history)
            scored_meals.append((meal, score))
        scored_meals.sort(key=lambda x: x[1], reverse=True)
        
        # Separate new vs past favorites
        new_suggestions = []
        past_favorites = []
        for meal, score in scored_meals:
            if any(item.get('food', '').lower() == meal.get('dish', '').lower() and item.get('rating', 0) >= 7 for item in food_choices_history):
                past_favorites.append((meal, score))
            else:
                new_suggestions.append((meal, score))
        
        personalized_meals_with_scores = []
        personalized_meals_with_scores.extend(new_suggestions)
        personalized_meals_with_scores.extend(past_favorites[:max(0, 5 - len(new_suggestions))])
        
        personalized_meals = []
        for meal, score in personalized_meals_with_scores:
            personalization_message = "Personalized suggestion"
            is_rated_before = any(item.get('food', '').lower() == meal.get('dish', '').lower() for item in food_choices_history)
            if is_rated_before:
                personalization_message = "This is a past favorite (You rated it highly before!)."
            personalized_meals.append({
                'dish': meal['dish'],
                'estimated_cals': int(meal['estimated_cals']),
                'focus': meal.get('focus', 'Balanced'),
                'personalization': personalization_message
            })
        
        if not personalized_meals:
            return {
                "message": "No new personalized suggestions found right now. Try different cuisine or meal type.",
                "target_range": f"{int(min_cals)}-{int(max_cals)} calories",
                "suggestions": [],
                "nutrition_tip": "Prefer whole foods, lean proteins, and complex carbs for sustained energy.",
                "learning_insight": user_preferences.get('insight', "Your agent is learning your preferences!")
            }
        
        return {
            "message": f"Here are {cuisine_preference.title() if cuisine_preference else 'Selected'} {meal_type.title()} suggestions for your {target_calories} calorie goal:",
            "target_range": f"{int(min_cals)}-{int(max_cals)} calories",
            "suggestions": personalized_meals,
            "nutrition_tip": "Focus on whole foods, lean proteins, and complex carbohydrates for sustained energy.",
            "learning_insight": user_preferences.get('insight', "Your agent is learning your preferences!")
        }
    except Exception as e:
        return {
            "message": f"Unable to generate meal suggestions: {str(e)}",
            "suggestions": []
        }

def analyze_fitness_meal_preferences(fitness_meal_history: list) -> Dict[str, Any]:
    """
    Analyze user's fitness meal ratings to learn preferences.
    
    Args:
        fitness_meal_history: List of fitness meal ratings
        
    Returns:
        Dictionary with learned preferences and insights
    """
    if not fitness_meal_history:
        return {
            "preferred_calories": "moderate",
            "preferred_protein": "moderate",
            "preferred_carbs": "moderate",
            "insight": "No fitness meal history yet. Your agent will learn as you rate meals!"
        }
    
    # Analyze calorie preferences
    high_rated_meals = [meal for meal in fitness_meal_history if meal.get('rating', 0) >= 7]
    low_rated_meals = [meal for meal in fitness_meal_history if meal.get('rating', 0) <= 4]
    
    if high_rated_meals:
        avg_high_rated_cals = sum(meal.get('estimated_cals', 0) for meal in high_rated_meals) / len(high_rated_meals)
        avg_low_rated_cals = sum(meal.get('estimated_cals', 0) for meal in low_rated_meals) / len(low_rated_meals) if low_rated_meals else 0
        
        if avg_high_rated_cals > avg_low_rated_cals:
            calorie_pref = "higher"
        elif avg_high_rated_cals < avg_low_rated_cals:
            calorie_pref = "lower"
        else:
            calorie_pref = "moderate"
    else:
        calorie_pref = "moderate"
    
    # Analyze meal type preferences
    meal_type_ratings = {}
    for meal in fitness_meal_history:
        meal_type = meal.get('meal_type', 'unknown')
        if meal_type not in meal_type_ratings:
            meal_type_ratings[meal_type] = []
        meal_type_ratings[meal_type].append(meal.get('rating', 5))
    
    preferred_meal_types = []
    for meal_type, ratings in meal_type_ratings.items():
        if len(ratings) >= 2 and sum(ratings) / len(ratings) >= 7:
            preferred_meal_types.append(meal_type)
    
    # Generate insight based on preferences
    if preferred_meal_types:
        insight = f"Your agent learned you prefer {', '.join(preferred_meal_types)} with {calorie_pref} calories!"
    else:
        insight = "Your agent is still learning your preferences. Keep rating meals!"
    
    return {
        "preferred_calories": calorie_pref,
        "preferred_meal_types": preferred_meal_types,
        "avg_high_rated_cals": avg_high_rated_cals if high_rated_meals else 0,
        "insight": insight
    }

def generate_personalized_fitness_meals(meal_type: str, min_cals: int, max_cals: int, 
                                      user_preferences: Dict[str, Any], high_rated_foods: list, cuisine_preference: str) -> list:
    """
    Generate personalized fitness meal suggestions based on user preferences.
    
    Args:
        meal_type: Type of meal
        min_cals: Minimum calories
        max_cals: Maximum calories
        user_preferences: User's learned preferences
        high_rated_foods: User's highly rated foods
        cuisine_preference: User's preferred cuisine
        
    Returns:
        List of personalized meal suggestions
    """
    # Base meal suggestions with calorie variations
    base_meals = get_all_fitness_meals(meal_type, cuisine_preference)
    
    # Personalize based on user preferences
    personalized_meals = []
    
    for meal in base_meals:
        # Adjust calories based on user preference
        if user_preferences.get('preferred_calories') == 'higher':
            adjusted_cals = min(meal['estimated_cals'] + 50, max_cals)
        elif user_preferences.get('preferred_calories') == 'lower':
            adjusted_cals = max(meal['estimated_cals'] - 50, min_cals)
        else:
            adjusted_cals = meal['estimated_cals']
        
        # Create personalized meal
        personalized_meal = {
            'dish': meal['dish'],
            'estimated_cals': adjusted_cals,
            'focus': meal['focus'],
            'personalization': f"Adjusted for your {user_preferences.get('preferred_calories', 'moderate')} calorie preference"
        }
        
        personalized_meals.append(personalized_meal)
    
    return personalized_meals

def get_all_fitness_meals(meal_type: str, cuisine_preference: str) -> list:
    """
    Get all available fitness meal suggestions for a meal type and cuisine.
    
    Args:
        meal_type: Type of meal
        cuisine_preference: User's preferred cuisine
        
    Returns:
        List of all available meal suggestions
    """
    # This dictionary now contains a comprehensive list of meals, categorized by type and cuisine.
    meal_suggestions = {
        "breakfast": [
            {"dish": "Oatmeal with fruits and nuts", "estimated_cals": 300, "focus": "High fiber, moderate protein"},
            {"dish": "Greek yogurt with berries", "estimated_cals": 250, "focus": "High protein, low carb"},
            {"dish": "Whole grain toast with avocado", "estimated_cals": 280, "focus": "Healthy fats, complex carbs"},
            {"dish": "Protein smoothie with banana", "estimated_cals": 320, "focus": "High protein, quick energy"},
            {"dish": "Quinoa breakfast bowl", "estimated_cals": 290, "focus": "Complete protein, fiber"},
            {"dish": "Chia pudding with almond milk", "estimated_cals": 260, "focus": "High fiber, omega-3"},
            {"dish": "Scrambled tofu with vegetables", "estimated_cals": 310, "focus": "High protein, vegetables"},
            {"dish": "Buckwheat pancakes with maple syrup", "estimated_cals": 340, "focus": "Gluten-free, moderate protein"}
        ],
        "lunch": [
            {"dish": "Quinoa bowl with vegetables", "estimated_cals": 400, "focus": "Complete protein, fiber"},
            {"dish": "Lentil soup with whole grain bread", "estimated_cals": 350, "focus": "Plant protein, complex carbs"},
            {"dish": "Chickpea salad with olive oil", "estimated_cals": 380, "focus": "Fiber, healthy fats"},
            {"dish": "Tofu stir-fry with brown rice", "estimated_cals": 420, "focus": "High protein, balanced carbs"},
            {"dish": "Bean and vegetable wrap", "estimated_cals": 360, "focus": "Fiber, moderate protein"},
            {"dish": "Mushroom and spinach risotto", "estimated_cals": 390, "focus": "Creamy, moderate protein"},
            {"dish": "Tempeh sandwich with sprouts", "estimated_cals": 370, "focus": "Fermented protein, fresh vegetables"},
            {"dish": "Vegetable curry with millet", "estimated_cals": 410, "focus": "Spicy, high fiber"}
        ],
        "dinner": [
            {"dish": "Grilled tofu with brown rice", "estimated_cals": 420, "focus": "Complete protein, whole grains"},
            {"dish": "Vegetable curry with quinoa", "estimated_cals": 380, "focus": "Fiber, moderate protein"},
            {"dish": "Stuffed bell peppers with lentils", "estimated_cals": 350, "focus": "Plant protein, vegetables"},
            {"dish": "Mushroom and spinach pasta", "estimated_cals": 400, "focus": "Moderate protein, complex carbs"},
            {"dish": "Cauliflower rice with tempeh", "estimated_cals": 340, "focus": "Low carb, high protein"},
            {"dish": "Lentil shepherd's pie", "estimated_cals": 430, "focus": "Comfort food, high protein"},
            {"dish": "Vegetable lasagna with cashew cheese", "estimated_cals": 450, "focus": "Italian comfort, moderate protein"},
            {"dish": "Stir-fried vegetables with seitan", "estimated_cals": 390, "focus": "High protein, colorful vegetables"}
        ],
        "snack": [
            {"dish": "Mixed nuts and dried fruits", "estimated_cals": 150, "focus": "Healthy fats, natural sugars"},
            {"dish": "Hummus with carrot sticks", "estimated_cals": 120, "focus": "Protein, fiber"},
            {"dish": "Apple with almond butter", "estimated_cals": 180, "focus": "Fiber, healthy fats"},
            {"dish": "Greek yogurt with honey", "estimated_cals": 140, "focus": "High protein, natural sweetener"},
            {"dish": "Edamame with sea salt", "estimated_cals": 130, "focus": "Complete protein, fiber"},
            {"dish": "Dark chocolate with almonds", "estimated_cals": 160, "focus": "Antioxidants, healthy fats"},
            {"dish": "Smoothie with protein powder", "estimated_cals": 200, "focus": "High protein, quick energy"},
            {"dish": "Rice cakes with avocado", "estimated_cals": 170, "focus": "Light, healthy fats"}
        ],
        "Indian": [
            {"dish": "Dal Khichdi with a side of yogurt", "estimated_cals": 350, "focus": "Indian, Protein, Carbs, Light meal"},
            {"dish": "Paneer Bhurji with whole wheat roti", "estimated_cals": 420, "focus": "Indian, Protein, Low carb"},
            {"dish": "Palak Paneer Gravy with Jowar Roti", "estimated_cals": 450, "focus": "Indian, Protein, Fiber"},
            {"dish": "Rajma Masala with Brown Rice", "estimated_cals": 480, "focus": "Indian, Protein, Fiber, Heavy meal"},
            {"dish": "Moong Dal Cheela with green chutney", "estimated_cals": 300, "focus": "Indian, Protein, Light meal"}
        ],
        "South Indian": [
            {"dish": "Masala Dosa with Sambar", "estimated_cals": 450, "focus": "South Indian, balanced meal"},
            {"dish": "Idli with Coconut Chutney", "estimated_cals": 250, "focus": "South Indian, light, easy to digest"},
            {"dish": "Uttapam with Onion and Tomato", "estimated_cals": 300, "focus": "South Indian, Carbs"},
            {"dish": "Rasam Rice with Aloo Poriyal", "estimated_cals": 400, "focus": "South Indian, Light meal"},
            {"dish": "Lemon Rice with Sambar", "estimated_cals": 380, "focus": "South Indian, Carbs, Light meal"}
        ],
        "Gujarati": [
            {"dish": "Gujarati Dal with Bajra Rotla", "estimated_cals": 400, "focus": "Gujarati, Fiber, Protein"},
            {"dish": "Dhokla with spicy green chutney", "estimated_cals": 200, "focus": "Gujarati, light, steamed snack"},
            {"dish": "Thepla with a side of yogurt", "estimated_cals": 320, "focus": "Gujarati, high fiber, iron"},
            {"dish": "Handvo with mixed vegetables", "estimated_cals": 450, "focus": "Gujarati, Fermented, Protein"},
            {"dish": "Khichu with oil and pickle", "estimated_cals": 350, "focus": "Gujarati, Light snack"}
        ],
        "Italian": [
            {"dish": "Veggie and Mushroom Pasta with Tomato Sauce", "estimated_cals": 480, "focus": "Italian, Carbs, Comfort food"},
            {"dish": "Minestrone Soup with whole grain bread", "estimated_cals": 300, "focus": "Italian, vegetables, light meal"},
            {"dish": "Margherita Pizza on whole wheat crust", "estimated_cals": 550, "focus": "Italian, Cheat meal"},
            {"dish": "Spinach and Ricotta Cannelloni", "estimated_cals": 520, "focus": "Italian, Protein, Comfort food"}
        ]
    }
    
    all_meals = []
    # If a specific cuisine is chosen, use only those meals
    if cuisine_preference and cuisine_preference != "Any":
        all_meals.extend(meal_suggestions.get(cuisine_preference.title(), []))
    
    # If no specific cuisine is selected, fall back to the generic meal type
    if not all_meals and meal_type:
        all_meals.extend(meal_suggestions.get(meal_type.lower(), []))
    
    return all_meals

def get_default_fitness_meals(meal_type: str, min_cals: int, max_cals: int) -> list:
    """
    Get default fitness meal suggestions.
    
    Args:
        meal_type: Type of meal
        min_cals: Minimum calories
        max_cals: Maximum calories
        
    Returns:
        List of default meal suggestions
    """
    # Fallback to a broader range if specific cuisine/preference lists are empty
    meal_suggestions = {
        "breakfast": [
            {"dish": "Oatmeal with fruits and nuts", "estimated_cals": 300, "focus": "High fiber, moderate protein"},
            {"dish": "Greek yogurt with berries", "estimated_cals": 250, "focus": "High protein, low carb"},
            {"dish": "Whole grain toast with avocado", "estimated_cals": 280, "focus": "Healthy fats, complex carbs"},
            {"dish": "Protein smoothie with banana", "estimated_cals": 320, "focus": "High protein, quick energy"},
            {"dish": "Quinoa breakfast bowl", "estimated_cals": 290, "focus": "Complete protein, fiber"}
        ],
        "lunch": [
            {"dish": "Quinoa bowl with vegetables", "estimated_cals": 400, "focus": "Complete protein, fiber"},
            {"dish": "Lentil soup with whole grain bread", "estimated_cals": 350, "focus": "Plant protein, complex carbs"},
            {"dish": "Chickpea salad with olive oil", "estimated_cals": 380, "focus": "Fiber, healthy fats"},
            {"dish": "Tofu stir-fry with brown rice", "estimated_cals": 420, "focus": "High protein, balanced carbs"},
            {"dish": "Bean and vegetable wrap", "estimated_cals": 360, "focus": "Fiber, moderate protein"}
        ],
        "dinner": [
            {"dish": "Grilled tofu with brown rice", "estimated_cals": 420, "focus": "Complete protein, whole grains"},
            {"dish": "Vegetable curry with quinoa", "estimated_cals": 380, "focus": "Fiber, moderate protein"},
            {"dish": "Stuffed bell peppers with lentils", "estimated_cals": 350, "focus": "Plant protein, vegetables"},
            {"dish": "Mushroom and spinach pasta", "estimated_cals": 400, "focus": "Moderate protein, complex carbs"},
            {"dish": "Cauliflower rice with tempeh", "estimated_cals": 340, "focus": "Low carb, high protein"}
        ],
        "snack": [
            {"dish": "Mixed nuts and dried fruits", "estimated_cals": 150, "focus": "Healthy fats, natural sugars"},
            {"dish": "Hummus with carrot sticks", "estimated_cals": 120, "focus": "Protein, fiber"},
            {"dish": "Apple with almond butter", "estimated_cals": 180, "focus": "Fiber, healthy fats"},
            {"dish": "Greek yogurt with honey", "estimated_cals": 140, "focus": "High protein, natural sweetener"},
            {"dish": "Edamame with sea salt", "estimated_cals": 130, "focus": "Complete protein, fiber"}
        ]
    }
    
    suggestions = meal_suggestions.get(meal_type.lower(), meal_suggestions["lunch"])
    
    # Filter suggestions based on calorie range
    filtered_suggestions = [
        s for s in suggestions 
        if min_cals <= s["estimated_cals"] <= max_cals
    ]
    
    if not filtered_suggestions:
        filtered_suggestions = suggestions[:2]  # Fallback to first 2 suggestions
    
    return filtered_suggestions

def save_fitness_meal_rating(user_id: str, mongo_client, meal_data: Dict[str, Any]) -> bool:
    """
    Save user's rating of a fitness meal suggestion for learning.
    
    Args:
        user_id: The user's ID
        mongo_client: MongoDB client connection
        meal_data: Dictionary containing meal rating data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        db = mongo_client["food_agent_db"]
        fitness_meals_collection = db["fitness_meals"]
        
        # Add metadata
        meal_data["user_id"] = user_id
        meal_data["timestamp"] = time.time()
        meal_data["rating_date"] = datetime.now()
        
        # Insert the rating
        fitness_meals_collection.insert_one(meal_data)
        
        return True
    except Exception as e:
        print(f"Error saving fitness meal rating: {e}")
        return False

def get_fitness_meal_insights(user_id: str, mongo_client) -> Dict[str, Any]:
    """
    Get insights about user's fitness meal preferences and progress.
    
    Args:
        user_id: The user's ID
        mongo_client: MongoDB client connection
        
    Returns:
        Dictionary with insights and recommendations
    """
    try:
        db = mongo_client["food_agent_db"]
        fitness_meals_collection = db["fitness_meals"]
        
        # Get recent fitness meal ratings
        recent_ratings = list(fitness_meals_collection.find({
            "user_id": user_id
        }).sort("timestamp", -1).limit(20))
        
        if not recent_ratings:
            return {
                "total_meals_rated": 0,
                "avg_rating": 0,
                "preferred_meal_types": [],
                "calorie_preferences": "moderate",
                "insights": ["Start rating your fitness meals to get personalized insights!"],
                "recommendations": ["Try different meal types to discover your preferences"]
            }
        
        # Calculate statistics
        total_meals = len(recent_ratings)
        avg_rating = sum(meal.get('rating', 5) for meal in recent_ratings) / total_meals
        
        # Analyze meal type preferences
        meal_type_ratings = {}
        for meal in recent_ratings:
            meal_type = meal.get('meal_type', 'unknown')
            if meal_type not in meal_type_ratings:
                meal_type_ratings[meal_type] = []
            meal_type_ratings[meal_type].append(meal.get('rating', 5))
        
        preferred_meal_types = []
        for meal_type, ratings in meal_type_ratings.items():
            if len(ratings) >= 2 and sum(ratings) / len(ratings) >= 7:
                preferred_meal_types.append(meal_type)
        
        # Analyze calorie preferences
        high_rated_meals = [meal for meal in recent_ratings if meal.get('rating', 0) >= 7]
        if high_rated_meals:
            avg_high_cals = sum(meal.get('estimated_cals', 0) for meal in high_rated_meals) / len(high_rated_meals)
            if avg_high_cals > 400:
                calorie_pref = "higher"
            elif avg_high_cals < 300:
                calorie_pref = "lower"
            else:
                calorie_pref = "moderate"
        else:
            calorie_pref = "moderate"
        
        # Generate insights
        insights = []
        if avg_rating >= 7:
            insights.append("Great job! You're finding meals that work well for you.")
        elif avg_rating >= 5:
            insights.append("You're on the right track. Keep experimenting with different options.")
        else:
            insights.append("Let's find meals that better suit your taste preferences.")
        
        if preferred_meal_types:
            insights.append(f"You seem to enjoy {', '.join(preferred_meal_types)} the most.")
        
        if calorie_pref != "moderate":
            insights.append(f"Your agent noticed you prefer {calorie_pref} calorie meals.")
        
        # Generate recommendations
        recommendations = []
        if len(preferred_meal_types) < 2:
            recommendations.append("Try exploring different meal types to diversify your nutrition.")
        
        if avg_rating < 7:
            recommendations.append("Consider adjusting portion sizes or trying different cooking methods.")
        
        recommendations.append("Keep rating meals to help your agent learn your preferences better!")
        
        return {
            "total_meals_rated": total_meals,
            "avg_rating": round(avg_rating, 1),
            "preferred_meal_types": preferred_meal_types,
            "calorie_preferences": calorie_pref,
            "insights": insights,
            "recommendations": recommendations
        }
        
    except Exception as e:
        return {
            "total_meals_rated": 0,
            "avg_rating": 0,
            "preferred_meal_types": [],
            "calorie_preferences": "moderate",
            "insights": [f"Unable to analyze preferences: {str(e)}"],
            "recommendations": ["Check back later for insights"]
        }

def save_fitness_goals(user_id: str, mongo_client, goals_data: Dict[str, Any]) -> bool:
    """
    Save user's fitness goals to the database.
    
    Args:
        user_id: The user's ID
        mongo_client: MongoDB client connection
        goals_data: Dictionary containing fitness goals
        
    Returns:
        True if successful, False otherwise
    """
    try:
        db = mongo_client["food_agent_db"]
        fitness_goals_collection = db["fitness_goals"]
        
        # Add timestamp and user_id
        goals_data["user_id"] = user_id
        goals_data["timestamp"] = time.time()
        goals_data["last_updated"] = datetime.now()
        
        # Update existing goals or insert new ones
        fitness_goals_collection.update_one(
            {"user_id": user_id},
            {"$set": goals_data},
            upsert=True
        )
        
        return True
    except Exception as e:
        print(f"Error saving fitness goals: {e}")
        return False

def get_fitness_goals(user_id: str, mongo_client) -> Optional[Dict[str, Any]]:
    """
    Retrieve user's fitness goals from the database.
    
    Args:
        user_id: The user's ID
        mongo_client: MongoDB client connection
        
    Returns:
        Dictionary with fitness goals or None if not found
    """
    try:
        db = mongo_client["food_agent_db"]
        fitness_goals_collection = db["fitness_goals"]
        
        goals = fitness_goals_collection.find_one({"user_id": user_id})
        return goals
    except Exception as e:
        print(f"Error retrieving fitness goals: {e}")
        return None

def get_workout_recovery_meal(user_id: str, mongo_client) -> str:
    """
    Get a specific workout recovery meal recommendation.
    
    Args:
        user_id: The user's ID
        mongo_client: MongoDB client connection
        
    Returns:
        A string with the recovery meal recommendation
    """
    try:
        db = mongo_client["food_agent_db"]
        food_collection = db["food_choices"]
        
        # Look for high-protein foods the user has rated highly
        high_rated_protein = list(food_collection.find({
            "user_id": user_id,
            "rating": {"$gte": 7},
            "category": "Protein is calling"
        }).sort("timestamp", -1).limit(3))
        
        if high_rated_protein:
            top_choice = high_rated_protein[0]
            return f"Perfect post-workout choice: {top_choice['food']} (You rated it {top_choice['rating']}/10!)"
        else:
            return "Consider a protein-rich meal from the 'Protein is calling' category for optimal recovery!"
            
    except Exception as e:
        return "Focus on protein-rich foods for workout recovery!"

def get_daily_activity_summary(user_id: str, mongo_client) -> Dict[str, Any]:
    """
    Get a summary of daily activity and food choices for better insights.
    
    Args:
        user_id: The user's ID
        mongo_client: MongoDB client connection
        
    Returns:
        A dictionary with daily summary information
    """
    try:
        db = mongo_client["food_agent_db"]
        food_collection = db["food_choices"]
        
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # Get today's food choices
        today_food = list(food_collection.find({
            "user_id": user_id,
            "timestamp": {
                "$gte": time.mktime(today_start.timetuple()),
                "$lte": time.mktime(today_end.timetuple())
            }
        }))
        
        if not today_food:
            return {
                "meals_today": 0,
                "avg_rating": 0,
                "categories": [],
                "message": "No meals logged today. Ready to start tracking?"
            }
        
        avg_rating = sum(item.get('rating', 5) for item in today_food) / len(today_food)
        categories = list(set(item.get('category', 'Unknown') for item in today_food))
        
        return {
            "meals_today": len(today_food),
            "avg_rating": round(avg_rating, 1),
            "categories": categories,
            "message": f"Today's summary: {len(today_food)} meals with average rating of {round(avg_rating, 1)}/10"
        }
        
    except Exception as e:
        return {
            "meals_today": 0,
            "avg_rating": 0,
            "categories": [],
            "message": "Unable to fetch today's summary. Check back later!"
        }

def calculate_meal_preference_score(meal: Dict[str, Any], user_preferences: Dict[str, Any], food_choices_history: list) -> float:
    """
    Calculate a preference score for a meal based on user preferences and history.
    
    Args:
        meal: Meal dictionary
        user_preferences: User's learned preferences
        food_choices_history: User's general food rating history
        
    Returns:
        Preference score (higher is better)
    """
    score = 0.0
    
    # Penalize meals that have been rated before to avoid repetition
    for item in food_choices_history:
        if item.get('food', '').lower() == meal.get('dish', '').lower():
            # Apply a heavy penalty if the food was disliked
            if item.get('rating', 5) <= 3:
                score -= 10.0
            # Apply a moderate penalty to foods that were liked to encourage trying new ones
            else:
                score -= 3.0
    
    # Base score from calorie preference
    if user_preferences.get('preferred_calories') == 'higher':
        if meal['estimated_cals'] > 350:
            score += 2.0
        elif meal['estimated_cals'] > 300:
            score += 1.0
    elif user_preferences.get('preferred_calories') == 'lower':
        if meal['estimated_cals'] < 300:
            score += 2.0
        elif meal['estimated_cals'] < 350:
            score += 1.0
    else:  # moderate
        if 280 <= meal['estimated_cals'] <= 420:
            score += 1.5
    
    # Score based on meal type preference
    if meal.get('meal_type') in user_preferences.get('preferred_meal_types', []):
        score += 3.0
    
    # Score based on focus preferences
    focus = meal.get('focus', '').lower()
    if 'protein' in focus and user_preferences.get('preferred_protein') == 'high':
        score += 2.0
    elif 'fiber' in focus and user_preferences.get('preferred_fiber') == 'high':
        score += 1.5
    
    # Score based on regional similarity
    if "south indian" in focus or "south indian" in meal.get('dish', '').lower():
        # Check if the user's food history contains a high-rated South Indian dish
        if any("south indian" in item.get('food', '').lower() and item.get('rating', 0) >= 7 for item in food_choices_history):
            score += 5.0
    if "gujarati" in focus or "gujarati" in meal.get('dish', '').lower():
        # Check if the user's food history contains a high-rated Gujarati dish
        if any("gujarati" in item.get('food', '').lower() and item.get('rating', 0) >= 7 for item in food_choices_history):
            score += 5.0

    return score

def get_personalized_meal_rotation(user_id: str, mongo_client, meal_type: str, target_calories: int, cuisine_preference: str, food_choices_history: list) -> list:
    """
    Get personalized meal suggestions with rotation to avoid repetition.
    
    Args:
        user_id: The user's ID
        mongo_client: MongoDB client connection
        meal_type: Type of meal
        target_calories: Target calories
        cuisine_preference: The user's preferred food type (e.g., "Protein", "Fiber")
        food_choices_history: User's general food rating history
        
    Returns:
        List of personalized meal suggestions
    """
    try:
        # Get user preferences
        fitness_meal_history = list(mongo_client["food_agent_db"]["fitness_meals"].find({"user_id": user_id}).sort("timestamp", -1).limit(50))
        user_preferences = analyze_fitness_meal_preferences(fitness_meal_history)
        
        # Get all available meals
        all_meals = get_all_fitness_meals(meal_type, cuisine_preference)
        
        # Filter meals based on calorie range
        min_cals = target_calories * 0.25
        max_cals = target_calories * 0.4
        
        calorie_filtered = [meal for meal in all_meals if min_cals <= meal['estimated_cals'] <= max_cals]
        
        # If not enough meals in the strict calorie range, expand it slightly
        if len(calorie_filtered) < 3:
            expanded_min = max(min_cals - 50, 0)
            expanded_max = max_cals + 50
            calorie_filtered = [meal for meal in all_meals if expanded_min <= meal['estimated_cals'] <= expanded_max]
            
        # Get dishes the user has rated before to avoid suggesting low-rated ones
        rated_dishes = {item.get('food', '').lower() for item in food_choices_history}
        disliked_dishes = {item.get('food', '').lower() for item in food_choices_history if item.get('rating', 0) <= 3}

        # Separate meals into new suggestions and past favorites
        new_suggestions = []
        past_favorites = []

        for meal in calorie_filtered:
            dish_name = meal.get('dish', '').lower()
            if dish_name in disliked_dishes:
                continue # Skip disliked dishes entirely

            if dish_name in rated_dishes:
                # This is a past favorite, check if it was highly rated
                if any(item.get('food', '').lower() == dish_name and item.get('rating', 0) >= 7 for item in food_choices_history):
                    past_favorites.append(meal)
            else:
                # This is a new suggestion
                new_suggestions.append(meal)

        # Combine new suggestions and a few of the top past favorites, prioritizing new ones
        final_suggestions_list = new_suggestions + past_favorites[:3]

        # Score and sort the final list
        scored_final_list = []
        for meal in final_suggestions_list:
            score = calculate_meal_preference_score(meal, user_preferences, food_choices_history)
            scored_final_list.append((meal, score))
        scored_final_list.sort(key=lambda x: x[1], reverse=True)

        personalized_meals = []
        
        for meal, score in scored_final_list:
            if meal.get('dish') in [s.get('dish') for s in personalized_meals]:
                continue # Skip if already in the list
            
            personalization_message = "Personalized suggestion"
            is_rated_before = any(item.get('dish', '').lower() == meal.get('dish', '').lower() for item in food_choices_history)
            if is_rated_before:
                 personalization_message = "This is a past favorite (You rated it highly before!)."

            personalized_meal = {
                'dish': meal['dish'],
                'estimated_cals': meal['estimated_cals'],
                'focus': meal['focus'],
                'personalization': personalization_message
            }
            personalized_meals.append(personalized_meal)
            
            if len(personalized_meals) >= 5:
                break
        
        # Fallback if no personalized meals are found
        if not personalized_meals:
            # Fallback to the top-scoring meal even if it's been rated before, but add a note
            if scored_final_list:
                top_meal, top_score = scored_final_list[0]
                return [{
                    'dish': top_meal['dish'],
                    'estimated_cals': top_meal['estimated_cals'],
                    'focus': top_meal['focus'],
                    'personalization': "This is a past favorite, as no new suggestions were found. Try logging more diverse meals to help your agent learn!"
                }]
            else:
                 return [{
                    'dish': 'No personalized suggestions found.',
                    'estimated_cals': 0,
                    'focus': 'N/A',
                    'personalization': 'Try logging more diverse meals to help your agent learn!'
                }]

        return personalized_meals
        
    except Exception as e:
        min_cals = target_calories * 0.25
        max_cals = target_calories * 0.4
        return get_default_fitness_meals(meal_type, min_cals, max_cals)
