# app/services/skill.py
from typing import List, Optional
from app.repositories.skill import SkillRepository
from app.models.skill import SkillCreate, SkillLevel, UserSkillEntry
from fastapi import HTTPException


names = [
        # Software & IT - Frontend (mapped to Software Development)
        {"name": "HTML", "category": "frontend", "industry": "Software Development"},
        {"name": "CSS", "category": "frontend", "industry": "Software Development"},
        {"name": "JavaScript", "category": "frontend", "industry": "Software Development"},
        {"name": "React", "category": "frontend", "industry": "Software Development"},
        {"name": "Angular", "category": "frontend", "industry": "Software Development"},
        {"name": "Vue.js", "category": "frontend", "industry": "Software Development"},
        {"name": "Next.js", "category": "frontend", "industry": "Software Development"},
        {"name": "UI Development", "category": "frontend", "industry": "Software Development"},

        # Software & IT - Backend (Software Development)
        {"name": "Python", "category": "backend", "industry": "Software Development"},
        {"name": "Django", "category": "backend", "industry": "Software Development"},
        {"name": "FastAPI", "category": "backend", "industry": "Software Development"},
        {"name": "Node.js", "category": "backend", "industry": "Software Development"},
        {"name": "Express.js", "category": "backend", "industry": "Software Development"},
        {"name": "Java", "category": "backend", "industry": "Software Development"},
        {"name": "Spring Boot", "category": "backend", "industry": "Software Development"},
        {"name": "PHP", "category": "backend", "industry": "Software Development"},
        {"name": "Laravel", "category": "backend", "industry": "Software Development"},

        # Software & IT - Mobile (Mobile App Development)
        {"name": "Flutter", "category": "mobile", "industry": "Mobile App Development"},
        {"name": "React Native", "category": "mobile", "industry": "Mobile App Development"},
        {"name": "Android (Kotlin)", "category": "mobile", "industry": "Mobile App Development"},
        {"name": "iOS (Swift)", "category": "mobile", "industry": "Mobile App Development"},

        # Software & IT - Database / Data (Data Science)
        {"name": "MySQL", "category": "database", "industry": "Data Science"},
        {"name": "PostgreSQL", "category": "database", "industry": "Data Science"},
        {"name": "MongoDB", "category": "database", "industry": "Data Science"},
        {"name": "NoSQL", "category": "database", "industry": "Data Science"},
        {"name": "Firebase", "category": "database", "industry": "Data Science"},
        {"name": "SQL", "category": "database", "industry": "Data Science"},

        # Software & IT - DevOps / Cloud
        {"name": "Docker", "category": "devops", "industry": "DevOps & Cloud Services"},
        {"name": "Kubernetes", "category": "devops", "industry": "DevOps & Cloud Services"},
        {"name": "AWS", "category": "devops", "industry": "DevOps & Cloud Services"},
        {"name": "Azure", "category": "devops", "industry": "DevOps & Cloud Services"},
        {"name": "GCP", "category": "devops", "industry": "DevOps & Cloud Services"},
        {"name": "CI/CD", "category": "devops", "industry": "DevOps & Cloud Services"},
        {"name": "Git", "category": "devops", "industry": "DevOps & Cloud Services"},

        # Software & IT - Other
        {"name": "REST APIs", "category": "backend", "industry": "Software Development"},
        {"name": "GraphQL", "category": "backend", "industry": "Software Development"},
        {"name": "Microservices", "category": "backend", "industry": "Software Development"},
        {"name": "System Design", "category": "backend", "industry": "Software Development"},

        # Design & Creative - Graphic Design
        {"name": "Graphic Design", "category": "graphic_design", "industry": "Graphic Design"},
        {"name": "Logo Design", "category": "graphic_design", "industry": "Logo & Brand Design"},
        {"name": "Brand Identity", "category": "graphic_design", "industry": "Logo & Brand Design"},
        {"name": "Business Cards", "category": "graphic_design", "industry": "Graphic Design"},
        {"name": "Social Media Design", "category": "graphic_design", "industry": "Graphic Design"},
        {"name": "Banner Design", "category": "graphic_design", "industry": "Graphic Design"},

        # Design & Creative - UI / UX
        {"name": "UI Design", "category": "ui_ux", "industry": "UI/UX Design"},
        {"name": "UX Research", "category": "ui_ux", "industry": "UI/UX Design"},
        {"name": "Wireframing", "category": "ui_ux", "industry": "UI/UX Design"},
        {"name": "Prototyping", "category": "ui_ux", "industry": "UI/UX Design"},
        {"name": "Figma", "category": "ui_ux", "industry": "UI/UX Design"},
        {"name": "Adobe XD", "category": "ui_ux", "industry": "UI/UX Design"},

        # Design & Creative - Illustration
        {"name": "Digital Illustration", "category": "illustration", "industry": "Graphic Design"},
        {"name": "Vector Art", "category": "illustration", "industry": "Graphic Design"},
        {"name": "Character Design", "category": "illustration", "industry": "Graphic Design"},

        # Design & Creative - Video & Animation
        {"name": "Video Editing", "category": "video_animation", "industry": "Video Editing"},
        {"name": "Motion Graphics", "category": "video_animation", "industry": "Animation & Motion Graphics"},
        {"name": "2D Animation", "category": "video_animation", "industry": "Animation & Motion Graphics"},
        {"name": "3D Animation", "category": "video_animation", "industry": "Animation & Motion Graphics"},
        {"name": "After Effects", "category": "video_animation", "industry": "Video Production"},
        {"name": "Premiere Pro", "category": "video_animation", "industry": "Video Production"},

        # Digital Marketing
        {"name": "SEO", "category": "marketing", "industry": "SEO (Search Engine Optimization)"},
        {"name": "SEM", "category": "marketing", "industry": "Digital Marketing"},
        {"name": "Google Ads", "category": "marketing", "industry": "Digital Marketing"},
        {"name": "Facebook Ads", "category": "marketing", "industry": "Digital Marketing"},
        {"name": "Instagram Ads", "category": "marketing", "industry": "Social Media Marketing"},
        {"name": "Social Media Marketing", "category": "marketing", "industry": "Social Media Marketing"},
        {"name": "Content Marketing", "category": "marketing", "industry": "Content Writing"},
        {"name": "Email Marketing", "category": "marketing", "industry": "Email Marketing"},
        {"name": "Affiliate Marketing", "category": "marketing", "industry": "Digital Marketing"},
        {"name": "Marketing Analytics", "category": "marketing", "industry": "Digital Marketing"},
        {"name": "Digital Marketing", "category": "marketing", "industry": "Digital Marketing"},

        # Writing & Translation - Writing
        {"name": "Content Writing", "category": "writing", "industry": "Content Writing"},
        {"name": "Blog Writing", "category": "writing", "industry": "Content Writing"},
        {"name": "Copywriting", "category": "writing", "industry": "Copywriting"},
        {"name": "Technical Writing", "category": "writing", "industry": "Technical Writing"},
        {"name": "UX Writing", "category": "writing", "industry": "UI/UX Design"},
        {"name": "Script Writing", "category": "writing", "industry": "Video Production"},

        # Writing & Translation - Editing
        {"name": "Proofreading", "category": "editing", "industry": "Others"},
        {"name": "Editing", "category": "editing", "industry": "Others"},

        # Writing & Translation - Translation
        {"name": "English Translation", "category": "translation", "industry": "Translation & Localization"},
        {"name": "Localization", "category": "translation", "industry": "Translation & Localization"},
        {"name": "Subtitling", "category": "translation", "industry": "Translation & Localization"},

        # Architecture & Engineering - Architecture
        {"name": "Architectural Design", "category": "architecture", "industry": "Architecture & Interior Design"},
        {"name": "AutoCAD", "category": "architecture", "industry": "Architecture & Interior Design"},
        {"name": "SketchUp", "category": "architecture", "industry": "Architecture & Interior Design"},
        {"name": "3D Rendering", "category": "architecture", "industry": "Architecture & Interior Design"},
        {"name": "Interior Design", "category": "architecture", "industry": "Architecture & Interior Design"},
        {"name": "3D Modeling", "category": "architecture", "industry": "Architecture & Interior Design"},

        # Architecture & Engineering - Engineering
        {"name": "Civil Engineering", "category": "engineering", "industry": "Engineering Services"},
        {"name": "Structural Design", "category": "engineering", "industry": "Engineering Services"},
        {"name": "Electrical Engineering", "category": "engineering", "industry": "Engineering Services"},
        {"name": "Mechanical Design", "category": "engineering", "industry": "Engineering Services"},
        {"name": "PCB Design", "category": "engineering", "industry": "Engineering Services"},
        {"name": "Embedded Systems", "category": "engineering", "industry": "Engineering Services"},

        # Business & Management
        {"name": "Project Management", "category": "management", "industry": "Project Management"},
        {"name": "Product Management", "category": "management", "industry": "Product Management"},
        {"name": "Business Analysis", "category": "management", "industry": "Business Analysis"},
        {"name": "Market Research", "category": "management", "industry": "Consulting Services"},
        {"name": "Agile Methodologies", "category": "management", "industry": "Project Management"},
        {"name": "Scrum", "category": "management", "industry": "Project Management"},
        {"name": "Jira", "category": "management", "industry": "Project Management"},
        {"name": "Documentation", "category": "management", "industry": "Technical Writing"},
        {"name": "Process Optimization", "category": "management", "industry": "Consulting Services"},

        # Sales & E-Commerce - E-Commerce
        {"name": "Shopify", "category": "ecommerce", "industry": "E-commerce Development"},
        {"name": "WooCommerce", "category": "ecommerce", "industry": "E-commerce Development"},
        {"name": "Magento", "category": "ecommerce", "industry": "E-commerce Development"},
        {"name": "Product Listing", "category": "ecommerce", "industry": "E-commerce Development"},
        {"name": "Store Setup", "category": "ecommerce", "industry": "E-commerce Development"},

        # Sales & E-Commerce - Sales
        {"name": "Lead Generation", "category": "sales", "industry": "Sales & Lead Generation"},
        {"name": "CRM Management", "category": "sales", "industry": "Sales & Lead Generation"},
        {"name": "Cold Emailing", "category": "sales", "industry": "Sales & Lead Generation"},
        {"name": "Sales Strategy", "category": "sales", "industry": "Sales & Lead Generation"},

        # Customer Support & Virtual Assistance
        {"name": "Live Chat Support", "category": "customer_support", "industry": "Customer Support"},
        {"name": "Email Support", "category": "customer_support", "industry": "Customer Support"},
        {"name": "Virtual Assistant", "category": "virtual_assistant", "industry": "Virtual Assistance"},
        {"name": "Data Entry", "category": "virtual_assistant", "industry": "Virtual Assistance"},
        {"name": "CRM Tools", "category": "virtual_assistant", "industry": "Virtual Assistance"},
        {"name": "Scheduling", "category": "virtual_assistant", "industry": "Virtual Assistance"},

        # Media & Content Creation
        {"name": "Photography", "category": "media", "industry": "Photography"},
        {"name": "Photo Editing", "category": "media", "industry": "Photography"},
        {"name": "Videography", "category": "media", "industry": "Video Production"},
        {"name": "Podcast Editing", "category": "media", "industry": "Voice Over"},
        {"name": "YouTube Content", "category": "media", "industry": "Video Production"},
        {"name": "Reels / Shorts Editing", "category": "media", "industry": "Video Editing"},

        # Mobile & Emerging Tech
        {"name": "AR / VR", "category": "emerging_tech", "industry": "Game Development"},
        {"name": "Blockchain", "category": "emerging_tech", "industry": "Blockchain Development"},
        {"name": "Smart Contracts", "category": "emerging_tech", "industry": "Blockchain Development"},
        {"name": "Web3", "category": "emerging_tech", "industry": "Blockchain Development"},
        {"name": "AI / ML", "category": "emerging_tech", "industry": "Machine Learning & AI"},
        {"name": "Data Science", "category": "emerging_tech", "industry": "Data Science"},
        {"name": "Prompt Engineering", "category": "emerging_tech", "industry": "Machine Learning & AI"},

        # Education & Consulting
        {"name": "Online Teaching", "category": "education", "industry": "Training & eLearning"},
        {"name": "Course Creation", "category": "education", "industry": "Training & eLearning"},
        {"name": "Tutoring", "category": "education", "industry": "Training & eLearning"},
        {"name": "Technical Consulting", "category": "consulting", "industry": "Consulting Services"},
        {"name": "Career Coaching", "category": "consulting", "industry": "Consulting Services"},
    ]

class SkillService:
    def __init__(self, repo: SkillRepository = None):
        self.repo = repo or SkillRepository()

    def seed_skills_if_missing(self) -> None:
        """names: list of dicts like {'name': 'Python', 'category': 'backend'}"""
        skills = [SkillCreate(**n) for n in names]
        self.repo.seed_skills(skills)

    def list_skills(self, category: Optional[str] = None) -> List[dict]:
        return self.repo.list_skills(category)

    def validate_user_skill_entries(self, entries: List[UserSkillEntry]) -> List[dict]:
        """Validate that skill_ids exist and level is valid. Return normalized list."""
        if not entries:
            return []

        skill_ids = [e.skill_id for e in entries]
        stored = {s["skill_id"]: s for s in self.repo.get_skills_by_ids(skill_ids)}
        result = []
        for e in entries:
            if e.skill_id not in stored:
                raise HTTPException(400, f"Skill not found: {e.skill_id}")
            if e.level not in SkillLevel:
                raise HTTPException(400, f"Invalid level for skill {e.skill_id}: {e.level}")
            result.append({"skill_id": e.skill_id, "level": e.level.value, "skill_name": stored[e.skill_id]["name"]})
        return result
