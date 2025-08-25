# MoOdMeNU 🍽️

**AI-Powered Food Recommendation System with Agentic Intelligence**

A personal project exploring agentic AI frameworks and the Model Context Protocol (MCP) - because who doesn't want their own AI food agents working together? 🚀 The system implements intelligent agents for food recommendations, period tracking, fitness monitoring, and meal planning, demonstrating how AI agents can collaborate to solve real-world problems (like figuring out what to eat when you're indecisive!).

## ✨ Core Features

- **Intelligent Food Learning**: AI-powered preference analysis and pattern recognition
- **Agentic Intelligence**: Multiple specialized AI agents working collaboratively (like a mini AI team!)
- **Mood-Based Recommendations**: Contextual meal suggestions for different situations
- **Adaptive Learning**: Gets smarter every time you use it - the more you interact, the better it gets!

## 🏗️ Technical Architecture

### **Frontend & Framework**
- **Streamlit**: Interactive web application interface (makes building UIs actually fun!)
- **Python**: Core application logic and data processing
- **Session State Management**: Persistent user preferences and application state

### **Backend & Database**
- **MongoDB**: NoSQL database for user data, food ratings, and agent interactions
- **PyMongo**: Database connectivity and query management
- **Data Collections**: User profiles, food preferences, agent data, and interaction history

### **AI & Agentic Systems**
- **Google Gemini AI**: Large language model for intelligent meal suggestions
- **Agentic Intelligence Framework**: Memory, perception, and planning systems (the brains behind the operation!)
- **Model Context Protocol**: Exploring structured AI agent communication and context management
- **Natural Language Processing**: Context-aware food recommendations and agent responses

### **Data Processing**
- **BMI Calculation**: Health metric analysis using standard formulas
- **Calorie Computation**: Mifflin-St Jeor equation for BMR and TDEE
- **Rating Analysis**: Statistical analysis of user preferences and agent performance

## 🤖 Agentic System Components

### **Core AI Agents**
- **Food Agent**: Intelligent meal recommendations and preference learning (your personal food guru!)
- **Period Tracker Agent**: Proactive health monitoring and meal suggestions
- **Fitness Agent**: Health metrics, calorie tracking, and activity-based recommendations
- **Meal Planner Agent**: Multi-day meal planning and variety management

### **Agentic Intelligence Framework**
- **Memory Systems**: Persistent learning and preference storage (remembers what you like!)
- **Perception Modules**: Context awareness and user state understanding
- **Planning Algorithms**: Strategic decision-making and recommendation generation
- **Collaborative Intelligence**: Agent coordination for comprehensive solutions

### **MCP Exploration**
- **Context Management**: Structured approach to AI agent context and memory
- **Agent Communication**: Exploring how agents can share and maintain context
- **Task Coordination**: Specialized agent assignment based on user needs
- **Response Aggregation**: Unified recommendations from multiple agent perspectives

## 🧩 System Components

### **Core Modules**
- `app.py`: Main Streamlit application and agent orchestration
- `fitness_agent.py`: Fitness tracking and health calculations
- `agentic_intelligence.py`: AI agent capabilities and learning systems
- `users.py`: User authentication and database management

### **Data Models**
- User profiles and preferences
- Food ratings and comments
- Agent interaction history
- Multi-agent recommendation data
- Learning and adaptation metrics

### **AI Learning System**
- Preference pattern analysis
- Agent performance optimization
- Multi-agent coordination learning
- Personalized scoring algorithms
- Collaborative recommendation strategies

## 🚀 Installation & Setup

### **Prerequisites**
- Python 3.8+
- MongoDB instance
- Google Gemini API key

### **Environment Configuration**
```bash
# Install dependencies
pip install -r requirements.txt

# Configure Streamlit secrets
# Create .streamlit/secrets.toml with GEMINI_API_KEY
```

### **Database Setup**
- Configure MongoDB connection in `users.py`
- Initialize required collections
- Set up user authentication system

## 🔧 Development & Customization

### **Extending Agentic Features**
- Add new specialized agents in dedicated modules
- Implement additional AI capabilities in `agentic_intelligence.py`
- Enhance agent communication protocols
- Customize UI components using Streamlit

### **AI Model Integration**
- Modify agent learning algorithms
- Add new recommendation strategies
- Implement advanced pattern recognition
- Extend MCP framework capabilities

## 📁 Project Structure
```
MoOdMeNU/
├── app.py                 # Main application and agent orchestration
├── fitness_agent.py       # Fitness agent implementation
├── agentic_intelligence.py # Core agentic AI framework
├── users.py              # User management
├── requirements.txt      # Dependencies
└── README.md            # This file
```

---

*MoOdMeNU - Exploring agentic AI and Model Context Protocol through intelligent food recommendation systems. Because sometimes you need AI agents to help you decide what's for dinner! 🍕✨*