# agentic_intelligence.py
# Modular agentic intelligence features for the food app

import streamlit as st
from datetime import datetime, timedelta
import time
from typing import List, Dict, Optional, Tuple

class FoodAgent:
    """Intelligent food agent that learns patterns and makes proactive suggestions"""
    
    def __init__(self, user_id: str, mongo_client):
        self.user_id = user_id
        self.mongo_client = mongo_client
        self.db = mongo_client["food_agent_db"]
        self.food_collection = self.db["food_choices"]
        self.period_collection = self.db["period_tracker"]
        
    def get_user_patterns(self) -> Dict:
        """Analyze user's eating patterns and preferences"""
        try:
            # Get user's food history
            history = list(self.food_collection.find({"user_id": self.user_id}).sort("timestamp", -1))
            
            if not history:
                return {"patterns": {}, "insights": []}
            
            patterns = {
                "category_preferences": {},
                "rating_patterns": {},
                "time_patterns": {},
                "cuisine_preferences": {},
                "recent_trends": []
            }
            
            # Analyze category preferences
            for item in history:
                category = item.get('category', 'Unknown')
                rating = item.get('rating', 5)
                
                if category not in patterns["category_preferences"]:
                    patterns["category_preferences"][category] = {"total": 0, "avg_rating": 0, "count": 0}
                
                cat_data = patterns["category_preferences"][category]
                cat_data["total"] += rating
                cat_data["count"] += 1
                cat_data["avg_rating"] = cat_data["total"] / cat_data["count"]
            
            # Analyze rating patterns
            high_rated = [item for item in history if item.get('rating', 0) >= 8]
            low_rated = [item for item in history if item.get('rating', 0) <= 3]
            
            patterns["rating_patterns"] = {
                "high_rated_foods": [item['food'] for item in high_rated[:5]],
                "low_rated_foods": [item['food'] for item in low_rated[:5]],
                "avg_rating": sum(item.get('rating', 5) for item in history) / len(history)
            }
            
            # Analyze time patterns (last 30 days)
            thirty_days_ago = time.time() - (30 * 24 * 60 * 60)
            recent_history = [item for item in history if item.get('timestamp', 0) > thirty_days_ago]
            
            if recent_history:
                patterns["recent_trends"] = [
                    f"Rated {item['food']} {item['rating']}/10" 
                    for item in recent_history[:5]
                ]
            
            return {"patterns": patterns, "insights": self._generate_insights(patterns, history)}
            
        except Exception as e:
            st.error(f"Error analyzing patterns: {e}")
            return {"patterns": {}, "insights": []}
    
    def _generate_insights(self, patterns: Dict, history: List) -> List[str]:
        """Generate human-readable insights from patterns"""
        insights = []
        
        if not patterns.get("category_preferences"):
            return ["No eating patterns detected yet. Start rating your food choices!"]
        
        # Category insights
        best_category = max(patterns["category_preferences"].items(), 
                          key=lambda x: x[1]["avg_rating"])
        worst_category = min(patterns["category_preferences"].items(), 
                           key=lambda x: x[1]["avg_rating"])
        
        insights.append(f"Your favorite category is '{best_category[0]}' with an average rating of {best_category[1]['avg_rating']:.1f}/10")
        insights.append(f"You might want to explore more options in '{worst_category[0]}' category")
        
        # Rating insights
        if patterns["rating_patterns"]["high_rated_foods"]:
            insights.append(f"Foods you loved: {', '.join(patterns['rating_patterns']['high_rated_foods'][:3])}")
        
        if patterns["rating_patterns"]["low_rated_foods"]:
            insights.append(f"Foods to avoid: {', '.join(patterns['rating_patterns']['low_rated_foods'][:3])}")
        
        # Recent activity insights
        if patterns["recent_trends"]:
            insights.append(f"Recent activity: {len(patterns['recent_trends'])} food choices in the last 30 days")
        
        return insights
    
    def get_proactive_suggestions(self) -> List[Dict]:
        """Generate proactive suggestions based on patterns and context"""
        suggestions = []
        
        try:
            # Get current context
            current_time = datetime.now()
            current_hour = current_time.hour
            current_day = current_time.strftime("%A")
            
            # Get user patterns
            user_data = self.get_user_patterns()
            patterns = user_data.get("patterns", {})
            
            # Time-based suggestions
            if 6 <= current_hour <= 10:
                suggestions.append({
                    "type": "breakfast",
                    "message": "Good morning! Time for a healthy start. Want some breakfast suggestions?",
                    "category": "Daily choices",
                    "priority": "high"
                })
            elif 11 <= current_hour <= 14:
                suggestions.append({
                    "type": "lunch",
                    "message": "Lunch time! Your agent noticed you usually prefer Indian food around this time.",
                    "category": "Daily choices",
                    "priority": "high"
                })
            elif 17 <= current_hour <= 20:
                suggestions.append({
                    "type": "dinner",
                    "message": "Evening cravings? Your agent has some comfort food suggestions ready.",
                    "category": "Daily choices",
                    "priority": "medium"
                })
            
            # Pattern-based suggestions
            if patterns.get("category_preferences"):
                best_category = max(patterns["category_preferences"].items(), 
                                  key=lambda x: x[1]["avg_rating"])
                
                if best_category[1]["count"] >= 3:
                    suggestions.append({
                        "type": "pattern",
                        "message": f"You've been loving '{best_category[0]}' lately! Want to explore more options?",
                        "category": best_category[0],
                        "priority": "medium"
                    })
            
            # Period-based suggestions (if applicable)
            if self.user_id == "Diya":
                period_suggestion = self._get_period_based_suggestion()
                if period_suggestion:
                    suggestions.append(period_suggestion)
            
            # Low activity reminder
            recent_activity = len([item for item in self.food_collection.find({"user_id": self.user_id}) 
                                 if item.get('timestamp', 0) > time.time() - (7 * 24 * 60 * 60)])
            
            if recent_activity < 3:
                suggestions.append({
                    "type": "reminder",
                    "message": "It's been a while since you logged your food choices. Want to help your agent learn your preferences?",
                    "category": "Daily choices",
                    "priority": "low"
                })
            
            return suggestions
            
        except Exception as e:
            st.error(f"Error generating proactive suggestions: {e}")
            return []
    
    def _get_period_based_suggestion(self) -> Optional[Dict]:
        """Get period-based proactive suggestions for Diya"""
        try:
            tracker_data = self.period_collection.find_one({"user_id": "Diya"})
            if not tracker_data:
                return None
            
            last_period_date = tracker_data.get('last_period_date')
            cycle_length = tracker_data.get('cycle_length', 28)
            
            if not last_period_date:
                return None
            
            if isinstance(last_period_date, datetime):
                last_period_date = last_period_date.date()
            
            today = datetime.now().date()
            days_since_last_period = (today - last_period_date).days
            days_to_next_period = cycle_length - days_since_last_period
            
            if days_to_next_period <= 2 and days_to_next_period > 0:
                return {
                    "type": "period_reminder",
                    "message": "Your period is approaching! Your agent suggests some comfort foods to prepare.",
                    "category": "Period is killing",
                    "priority": "high"
                }
            elif days_since_last_period <= 5:  # Assuming 5-day period
                return {
                    "type": "period_support",
                    "message": "You're on your period. Your agent has some mood-lifting food suggestions!",
                    "category": "Period is killing",
                    "priority": "high"
                }
            
            return None
            
        except Exception as e:
            return None
    
    def get_smart_recommendations(self, category: str, limit: int = 3) -> List[Dict]:
        """Get smart recommendations based on user patterns and category"""
        try:
            # Get user's history for this category
            category_history = list(self.food_collection.find({
                "user_id": self.user_id,
                "category": category
            }).sort("rating", -1))
            
            if not category_history:
                return []
            
            # Get high-rated foods from this category
            high_rated = [item for item in category_history if item.get('rating', 0) >= 7]
            
            # Get foods not tried yet (if any)
            tried_foods = {item['food'] for item in category_history}
            
            recommendations = []
            
            # Add high-rated foods as "you might also like"
            for item in high_rated[:2]:
                recommendations.append({
                    "food": item['food'],
                    "reason": f"You rated this {item['rating']}/10 - you might want to try it again!",
                    "confidence": "high"
                })
            
            # Add pattern-based suggestions
            if len(recommendations) < limit:
                user_data = self.get_user_patterns()
                patterns = user_data.get("patterns", {})
                
                if patterns.get("category_preferences"):
                    # Suggest from user's best category
                    best_category = max(patterns["category_preferences"].items(), 
                                      key=lambda x: x[1]["avg_rating"])
                    
                    if best_category[0] != category and best_category[1]["avg_rating"] >= 7:
                        recommendations.append({
                            "food": f"Something from {best_category[0]} category",
                            "reason": f"You usually love {best_category[0]} foods (avg rating: {best_category[1]['avg_rating']:.1f}/10)",
                            "confidence": "medium"
                        })
            
            return recommendations[:limit]
            
        except Exception as e:
            st.error(f"Error getting smart recommendations: {e}")
            return []

def initialize_agentic_features(user_id: str, mongo_client):
    """Initialize agentic features for a user"""
    return FoodAgent(user_id, mongo_client)

def display_agentic_dashboard(agent: FoodAgent):
    """Display the agentic intelligence dashboard"""
    st.header("🤖 Your AI Food Agent Dashboard")
    st.markdown("Your agent is learning your patterns and making smart suggestions!")
    
    # Get user patterns and insights
    with st.spinner("Your agent is analyzing your patterns..."):
        user_data = agent.get_user_patterns()
    
    if user_data["patterns"]:
        # Display insights
        st.subheader("💡 Your Agent's Insights")
        for insight in user_data["insights"]:
            st.info(insight)
        
        # Display proactive suggestions
        st.subheader("🚀 Proactive Suggestions")
        suggestions = agent.get_proactive_suggestions()
        
        if suggestions:
            for suggestion in suggestions:
                priority_color = {
                    "high": "🔴",
                    "medium": "🟡", 
                    "low": "🟢"
                }.get(suggestion["priority"], "⚪")
                
                st.markdown(f"{priority_color} **{suggestion['type'].title()}**: {suggestion['message']}")
                
                if suggestion.get("category"):
                    if st.button(f"Get {suggestion['category']} suggestions", 
                               key=f"suggestion_{suggestion['type']}"):
                        st.session_state.auto_category = suggestion['category']
                        st.rerun()
        else:
            st.success("All caught up! Your agent will notify you when there are new suggestions.")
    else:
        st.info("Your agent needs more data to learn your patterns. Start rating your food choices!")
    
    # Smart recommendations section
    st.subheader("🧠 Smart Recommendations")
    category_for_recs = st.selectbox(
        "Get smart recommendations for category:",
        ["Daily choices", "Protein is calling", "Period is killing", "Desserts", "Cheat meals", "Exams"],
        key="smart_recs_category"
    )
    
    if st.button("Get Smart Recommendations", key="get_smart_recs"):
        with st.spinner("Your agent is thinking..."):
            recommendations = agent.get_smart_recommendations(category_for_recs)
        
        if recommendations:
            st.success(f"Smart recommendations for {category_for_recs}:")
            for rec in recommendations:
                confidence_icon = "🟢" if rec["confidence"] == "high" else "🟡"
                st.markdown(f"{confidence_icon} **{rec['food']}**")
                st.caption(f"Reason: {rec['reason']}")
        else:
            st.info("No specific recommendations yet. Your agent is still learning your preferences!")

# Example usage functions that can be called from main app
def get_quick_insight(user_id: str, mongo_client) -> str:
    """Get a quick insight for display in sidebar or main area"""
    try:
        agent = FoodAgent(user_id, mongo_client)
        user_data = agent.get_user_patterns()
        
        if user_data["insights"]:
            return user_data["insights"][0]  # Return first insight
        return "Your agent is learning your food preferences!"
    except:
        return "Your agent is ready to help!"

def get_proactive_notification(user_id: str, mongo_client) -> Optional[Dict]:
    """Get a single proactive notification for display"""
    try:
        agent = FoodAgent(user_id, mongo_client)
        suggestions = agent.get_proactive_suggestions()
        
        if suggestions:
            # Return highest priority suggestion
            high_priority = [s for s in suggestions if s["priority"] == "high"]
            if high_priority:
                return high_priority[0]
            return suggestions[0]
        return None
    except:
        return None 
