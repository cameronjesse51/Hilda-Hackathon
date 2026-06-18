import sys

def resolve_app_py():
    with open("backend/app.py", "r") as f:
        content = f.read()

    # Block 1
    target1 = """<<<<<<< HEAD
schools_path = Path(__file__).parent / "schools.json"
with open(schools_path) as f:
    SCHOOLS_DATA = json.load(f)
=======
profiles: dict[str, dict] = {}
conversations: dict[str, list] = {}

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
>>>>>>> e3c1db1 (lots of things)"""
    replacement1 = """import json
from pathlib import Path
schools_path = Path(__file__).parent / "schools.json"
with open(schools_path) as f:
    SCHOOLS_DATA = json.load(f)

profiles: dict[str, dict] = {}
conversations: dict[str, list] = {}

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])"""
    content = content.replace(target1, replacement1)

    # Block 2
    target2 = """<<<<<<< HEAD
    updated_profile["session_history"] = updated_history
    await db.save_profile(updated_profile)
=======
    updated_profile["last_active_at"] = time.time()
    profiles[req.student_id] = updated_profile
    conversations[req.student_id] = updated_history
>>>>>>> e3c1db1 (lots of things)"""
    replacement2 = """    updated_profile["session_history"] = updated_history
    updated_profile["last_active_at"] = time.time()
    await db.save_profile(updated_profile)
    
    profiles[req.student_id] = updated_profile
    conversations[req.student_id] = updated_history"""
    content = content.replace(target2, replacement2)

    # Block 3
    target3 = """<<<<<<< HEAD

        profile["session_history"] = history
        await db.save_profile(profile)
=======
        profile["last_active_at"] = time.time()
        profiles[req.student_id] = profile
        conversations[req.student_id] = history
>>>>>>> e3c1db1 (lots of things)"""
    replacement3 = """        profile["session_history"] = history
        profile["last_active_at"] = time.time()
        await db.save_profile(profile)
        
        profiles[req.student_id] = profile
        conversations[req.student_id] = history"""
    content = content.replace(target3, replacement3)

    # Block 4
    target4 = """<<<<<<< HEAD
    await db.save_profile(profile)
=======
    # Pre-extract goals text into the profile before Claude ever sees it
    if req.goals:
        profile = _extract_goals_into_profile(profile, req.goals)
>>>>>>> e3c1db1 (lots of things)"""
    replacement4 = """    # Pre-extract goals text into the profile before Claude ever sees it
    if req.goals:
        profile = _extract_goals_into_profile(profile, req.goals)
        
    await db.save_profile(profile)"""
    content = content.replace(target4, replacement4)

    with open("backend/app.py", "w") as f:
        f.write(content)


def resolve_requirements():
    with open("backend/requirements.txt", "r") as f:
        content = f.read()
    target = """<<<<<<< HEAD
=======
google-genai

openai
>>>>>>> e3c1db1 (lots of things)"""
    replacement = """google-genai
openai"""
    content = content.replace(target, replacement)
    with open("backend/requirements.txt", "w") as f:
        f.write(content)

def resolve_app_jsx():
    with open("src/App.jsx", "r") as f:
        content = f.read()

    # Block 1
    target1 = """<<<<<<< HEAD
const API_URL = import.meta.env.VITE_API_URL || ''
=======
const rawEnvUrl = import.meta.env.VITE_API_URL
const isEnvSms = rawEnvUrl && (rawEnvUrl.includes(':3001') || rawEnvUrl.includes('textbelt'))

const API_URL = isEnvSms ? 'http://localhost:8000' : (rawEnvUrl || 'http://localhost:8000')
const SMS_API_URL = import.meta.env.VITE_SMS_API_URL || (isEnvSms ? rawEnvUrl : 'http://localhost:3001')
>>>>>>> e3c1db1 (lots of things)"""
    replacement1 = """const rawEnvUrl = import.meta.env.VITE_API_URL || ''
const isEnvSms = rawEnvUrl && (rawEnvUrl.includes(':3001') || rawEnvUrl.includes('textbelt'))

const API_URL = isEnvSms ? 'http://localhost:8000' : (rawEnvUrl || 'http://localhost:8000')
const SMS_API_URL = import.meta.env.VITE_SMS_API_URL || (isEnvSms ? rawEnvUrl : 'http://localhost:3001')"""
    content = content.replace(target1, replacement1)

    # Block 2
    target2 = """<<<<<<< HEAD
  const [profile, setProfile] = useState(initialProfile || null)
  const [onboardingStep, setOnboardingStep] = useState(initialProfile ? 'done' : 'name')
=======
  const [onboardingLoading, setOnboardingLoading] = useState(false)
  const [profile, setProfile] = useState(null)
  const [onboardingStep, setOnboardingStep] = useState('name')
>>>>>>> e3c1db1 (lots of things)"""
    replacement2 = """  const [onboardingLoading, setOnboardingLoading] = useState(false)
  const [profile, setProfile] = useState(initialProfile || null)
  const [onboardingStep, setOnboardingStep] = useState(initialProfile ? 'done' : 'name')"""
    content = content.replace(target2, replacement2)

    # Block 3
    target3 = """<<<<<<< HEAD
    const apiUrl = API_URL
=======
>>>>>>> e3c1db1 (lots of things)"""
    replacement3 = """    const apiUrl = API_URL"""
    content = content.replace(target3, replacement3)

    # Block 4
    target4 = """<<<<<<< HEAD
      const response = await fetch(`${API_URL}/api/verify-code`, {
=======
      const response = await fetch(`${SMS_API_URL}/api/verify-code`, {
>>>>>>> e3c1db1 (lots of things)"""
    replacement4 = """      const response = await fetch(`${SMS_API_URL}/api/verify-code`, {"""
    content = content.replace(target4, replacement4)

    with open("src/App.jsx", "w") as f:
        f.write(content)

if __name__ == "__main__":
    resolve_app_py()
    resolve_requirements()
    resolve_app_jsx()
    print("Resolved conflicts.")
