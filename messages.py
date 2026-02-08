# Copyright Polymorph Corporation (2026)

"""
Centralized message strings for ProfileGPT.

This module contains all user-facing text responses to make
maintenance and updates easier. Extract strings from code logic
for better separation of concerns.
"""

# Help/meta-query responses
HELP_RESPONSE = """This is Ask Eric - an AI assistant that represents Eric Bell's professional background and expertise.

**What you can ask about:**
- Eric's technical skills, programming languages, and tools
- Work history, job roles, and career progression
- Notable projects, achievements, and accomplishments
- Subject matter expertise (DevOps, infrastructure, cloud, etc.)
- Working style, values, and leadership approach
- Professional development and learning
- How Eric would approach specific technical challenges

**What's out of scope:**
- Personal life (family, hobbies, favorites)
- Unrelated topics (weather, sports, politics)
- Off-topic requests (math problems, translations)

**Two ways to interact:**
1. **Chat with Eric** - Ask questions about his professional background
2. **Check Job Fit** - Paste a job description to see how well Eric matches

Ask away! I'm here to help you understand Eric's professional profile."""

# Meta-question variations that trigger help response
META_QUESTIONS = [
    "how do i use this?",
    "how do i use this",
    "what is this?",
    "what is this",
    "how does this work?",
    "how does this work"
]

# Out-of-scope refusal responses (rotated randomly)
REFUSAL_RESPONSES = [
    "I'm focused on Eric's professional background. Ask me about his experience, projects, or technical skills!",
    "That's outside my scope, but I can help with questions about Eric's work history, expertise, or professional values.",
    "I only discuss Eric's professional life. Try asking about his technical background or notable projects!",
    "I specialize in Eric's professional profile. Ask about his technical expertise, work experience, or how he approaches problems.",
    "Not my area—I'm here for Eric's career and professional development. What would you like to know about his background?",
    "I focus on Eric's professional side. Happy to discuss his skills, projects, or working style!",
    "That's beyond my scope. I can tell you about Eric's technical experience, leadership approach, or career highlights.",
]

# Warning message template (when approaching out-of-scope limit)
WARNING_MESSAGE = "You're straying away from Eric's professional life too much. I'll cut you off if you continue."

# Cutoff message template (when limit reached)
CUTOFF_MESSAGE = "You have asked too many off-topic questions. This session has been limited."
