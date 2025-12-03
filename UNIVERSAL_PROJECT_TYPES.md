# Universal Project Types Support

## Problem
The AI questions were too focused on **software/web development** projects, asking about "landing pages," "features," "technical requirements," etc. This didn't work well for other types of freelance work like design, writing, marketing, video editing, consulting, etc.

## Solution
Updated the AI prompts to be **universal** and adapt to **any type of freelance project** across all industries.

---

## What Changed

### 1. **Question Generation Prompt** ✅

**Before (Software-Focused):**
```python
prompt = (
    "You are an AI discovery assistant. Ask the next clarifying question to define a project scope.\n"
    "Focus on: features, timeline preferences, technical requirements, design needs, target audience, platform preferences, "
    "and budget expectations (ask for budget range or preference like 'tight budget', 'moderate', 'premium' - NOT exact amounts).\n"
    ...
)
```

**After (Universal):**
```python
prompt = (
    "You are an AI discovery assistant helping clients define their project requirements for ANY type of freelance work "
    "(software, design, writing, marketing, video, consulting, etc.).\n\n"
    "Ask the next clarifying question based on the project type. Focus on:\n"
    "- What specific deliverables/outcomes they want\n"
    "- Timeline and deadline preferences\n"
    "- Target audience or purpose\n"
    "- Style, tone, or quality expectations\n"
    "- Budget expectations (ask for range or preference: 'tight budget', 'moderate', 'premium' - NOT exact amounts)\n"
    "- Any specific requirements or constraints\n\n"
    "Adapt your questions to the project type mentioned. For example:\n"
    "- Software/Web: features, platform, technical needs\n"
    "- Design: style, dimensions, format, revisions\n"
    "- Writing: word count, tone, SEO, research depth\n"
    "- Marketing: channels, goals, audience demographics\n"
    "- Video: length, style, editing level, deliverable format\n\n"
    ...
)
```

---

### 2. **Suggestion Generation Prompt** ✅

**Before (Software-Focused):**
```python
instructions = (
    "You are an AI solutions architect. Based on the information, craft JSON with keys:\n"
    "scope_summary (string), content_sections (array of strings describing deliverables), "
    "key_features (array of strings), tone (string), "
    ...
    "7. Typical ranges: Simple (₹50k-₹150k), Moderate (₹150k-₹350k), Complex (₹350k-₹800k)\n\n"
)
```

**After (Universal):**
```python
instructions = (
    "You are an AI project strategist for ANY type of freelance work (software, design, writing, marketing, video, consulting, etc.). "
    "Based on the information, craft JSON with keys:\n"
    "scope_summary (string - comprehensive summary of the project), "
    "content_sections (array of strings describing deliverables/components), "
    "key_features (array of strings - main requirements, outcomes, or specifications), "
    ...
    "ADAPT TO PROJECT TYPE:\n"
    "- Software/Web: features → technical features, integrations\n"
    "- Design: features → design elements, deliverables, revisions\n"
    "- Writing: features → content pieces, word count, topics\n"
    "- Marketing: features → campaigns, channels, strategies\n"
    "- Video: features → video segments, editing techniques, final outputs\n"
    "- Consulting: features → deliverables, sessions, reports\n\n"
    ...
    "7. Typical ranges vary by type:\n"
    "   - Software/Web: Simple (₹50k-₹150k), Moderate (₹150k-₹350k), Complex (₹350k-₹800k)\n"
    "   - Design/Creative: Simple (₹20k-₹80k), Moderate (₹80k-₹200k), Complex (₹200k-₹500k)\n"
    "   - Writing/Content: Simple (₹10k-₹50k), Moderate (₹50k-₹150k), Complex (₹150k-₹400k)\n"
    "   - Marketing: Simple (₹30k-₹100k), Moderate (₹100k-₹300k), Complex (₹300k-₹800k)\n\n"
)
```

---

### 3. **System Messages** ✅

**Questions:**
- Before: `"You are a helpful project scope assistant."`
- After: `"You are a helpful project scope assistant for any type of freelance work across all industries."`

**Suggestions:**
- Before: `"You are a concise project strategist who responds with JSON only."`
- After: `"You are a concise project strategist for all types of freelance work who responds with JSON only."`

---

## Now Supports All Project Types

### 🖥️ **Software & Web Development**
**Example Project:** "Build a restaurant ordering website"
- Questions: features, platform, integrations, tech stack
- Budget: ₹50k-₹800k
- Deliverables: website, admin panel, mobile responsive

### 🎨 **Graphic Design**
**Example Project:** "Design a logo and brand identity"
- Questions: style preferences, color schemes, file formats, revisions
- Budget: ₹20k-₹500k
- Deliverables: logo files, brand guidelines, mockups

### ✍️ **Content Writing**
**Example Project:** "Write 10 blog posts for my business"
- Questions: word count, tone, SEO requirements, topics, research depth
- Budget: ₹10k-₹400k
- Deliverables: articles, SEO optimization, images

### 📱 **Digital Marketing**
**Example Project:** "Social media marketing campaign"
- Questions: platforms, goals, target audience, duration, content types
- Budget: ₹30k-₹800k
- Deliverables: content calendar, posts, analytics, ad campaigns

### 🎥 **Video Editing**
**Example Project:** "Edit 5 YouTube videos"
- Questions: length, style, transitions, music, deliverable format
- Budget: ₹20k-₹300k
- Deliverables: edited videos, thumbnails, subtitles

### 💼 **Business Consulting**
**Example Project:** "Market research and strategy"
- Questions: scope of research, deliverable format, timeline, depth
- Budget: ₹50k-₹500k
- Deliverables: reports, presentations, recommendations

### 📸 **Photography**
**Example Project:** "Product photography for e-commerce"
- Questions: number of products, angles, editing level, usage rights
- Budget: ₹15k-₹200k
- Deliverables: edited photos, different formats

### 🌐 **Translation**
**Example Project:** "Translate website content to 3 languages"
- Questions: word count, languages, specialized terminology, deadline
- Budget: ₹10k-₹150k
- Deliverables: translated content, localization notes

### 📊 **Data Analysis**
**Example Project:** "Analyze sales data and create dashboard"
- Questions: data sources, metrics, visualization needs, tools
- Budget: ₹40k-₹400k
- Deliverables: dashboard, insights report, recommendations

### 🎵 **Audio Production**
**Example Project:** "Produce a podcast series"
- Questions: episodes, length, editing level, music, hosting
- Budget: ₹20k-₹300k
- Deliverables: edited episodes, intro/outro, show notes

---

## How AI Adapts to Project Type

### Example 1: Software Project

**User Input:** "Build a mobile app for fitness tracking"

**AI Questions:**
1. "What are the core features you want in your fitness tracking app (e.g., workout logging, calorie tracking, progress charts)?"
2. "Do you need the app for iOS, Android, or both platforms?"
3. "Should the app integrate with wearables like Fitbit or Apple Watch?"
4. "What's your budget expectation for this project - tight, moderate, or premium?"
5. "What's your target timeline for the app launch?"

**AI Suggestion:**
- **Scope Summary:** Full-featured fitness tracking mobile app with workout logging, calorie tracking, and progress analytics
- **Content Sections:** User authentication, workout library, calorie database, progress dashboard, settings
- **Key Features:** Cross-platform (iOS/Android), wearable integration, cloud sync, offline mode
- **Budget:** ₹350,000 (Moderate-Complex)
- **Timeline:** 16 weeks

---

### Example 2: Design Project

**User Input:** "Design packaging for my organic tea brand"

**AI Questions:**
1. "What specific packaging items do you need designed (e.g., tea boxes, pouches, labels, inserts)?"
2. "What design style are you envisioning - minimalist, vintage, modern, traditional?"
3. "How many product variants or flavors need packaging designs?"
4. "What's your budget expectation - tight, moderate, or premium?"
5. "Do you need print-ready files or just digital mockups?"

**AI Suggestion:**
- **Scope Summary:** Complete packaging design suite for organic tea brand with eco-friendly aesthetic
- **Content Sections:** Primary packaging, label design, pattern elements, typography system
- **Key Features:** 4 tea variants, eco-friendly design, print-ready files, 3D mockups, 2 revision rounds
- **Budget:** ₹120,000 (Moderate)
- **Timeline:** 6 weeks

---

### Example 3: Writing Project

**User Input:** "Write content for my law firm website"

**AI Questions:**
1. "What pages or sections need content (e.g., homepage, services, about, practice areas)?"
2. "What tone should the content have - formal and authoritative, or approachable and friendly?"
3. "Approximately how many words of content do you need in total?"
4. "Should the content be SEO-optimized with specific keywords?"
5. "What's your budget range for this writing project?"

**AI Suggestion:**
- **Scope Summary:** Professional website content for law firm with SEO optimization and client-focused messaging
- **Content Sections:** Homepage (500 words), 6 practice area pages (800 words each), About page (600 words), Contact page (300 words)
- **Key Features:** SEO keyword integration, legal expertise positioning, client testimonial integration, CTA optimization
- **Budget:** ₹85,000 (Moderate)
- **Timeline:** 4 weeks

---

### Example 4: Marketing Project

**User Input:** "Social media marketing for my new café"

**AI Questions:**
1. "Which social media platforms do you want to focus on (Instagram, Facebook, Twitter, TikTok)?"
2. "What are your main goals - brand awareness, foot traffic, online orders, or engagement?"
3. "How often do you want to post content - daily, 3 times/week, or custom schedule?"
4. "Do you need content creation (photos/videos) or just strategy and captions?"
5. "What's your budget expectation for this marketing campaign?"

**AI Suggestion:**
- **Scope Summary:** Comprehensive social media marketing campaign for café launch with content creation and community management
- **Content Sections:** Content calendar, Instagram posts & stories, Facebook posts, TikTok videos, engagement strategy
- **Key Features:** 3 posts/week for 3 months, professional food photography, reel/TikTok creation, hashtag strategy, monthly analytics
- **Budget:** ₹180,000 (Moderate)
- **Timeline:** 12 weeks (3 months)

---

### Example 5: Video Project

**User Input:** "Edit my wedding video"

**AI Questions:**
1. "What's the total raw footage duration you have?"
2. "How long should the final edited video be (e.g., 10 min highlight, 45 min full ceremony)?"
3. "What editing style do you prefer - cinematic, documentary, traditional, or modern with effects?"
4. "Do you want color grading, music, subtitles, or special effects?"
5. "What's your budget range for this video editing project?"

**AI Suggestion:**
- **Scope Summary:** Professional wedding video editing with cinematic style, color grading, and music
- **Content Sections:** Ceremony highlights (15 min), reception highlights (10 min), full ceremony (60 min), teaser (2 min)
- **Key Features:** Cinematic color grading, licensed music, slow-motion effects, title cards, 4K output, 2 revision rounds
- **Budget:** ₹65,000 (Moderate)
- **Timeline:** 4 weeks

---

## Budget Ranges by Project Type

| Project Type | Simple | Moderate | Complex |
|--------------|--------|----------|---------|
| **Software/Web Development** | ₹50k-₹150k | ₹150k-₹350k | ₹350k-₹800k+ |
| **Design/Creative** | ₹20k-₹80k | ₹80k-₹200k | ₹200k-₹500k |
| **Writing/Content** | ₹10k-₹50k | ₹50k-₹150k | ₹150k-₹400k |
| **Marketing/Social Media** | ₹30k-₹100k | ₹100k-₹300k | ₹300k-₹800k |
| **Video/Audio** | ₹20k-₹80k | ₹80k-₹250k | ₹250k-₹600k |
| **Consulting/Strategy** | ₹40k-₹120k | ₹120k-₹350k | ₹350k-₹800k+ |

---

## Benefits

### ✅ **Universal Coverage**
- Works for **any type** of freelance work
- AI adapts questions based on project context
- No need for separate flows per category

### ✅ **Intelligent Adaptation**
- AI recognizes project type from user input
- Asks relevant questions for that specific domain
- Uses appropriate terminology (features vs deliverables vs content pieces)

### ✅ **Accurate Budget Ranges**
- Different budget ranges for different project types
- Design projects typically cost less than software
- Marketing campaigns have different pricing models

### ✅ **Better User Experience**
- Questions feel natural and relevant
- Users don't get confused by irrelevant tech jargon
- Increases trust and completion rate

---

## Testing Different Project Types

### Test Case 1: Software
**Input:** "Build an e-commerce website"
**Expected:** Questions about features, platform, payment integration, inventory management

### Test Case 2: Design
**Input:** "Create a logo for my startup"
**Expected:** Questions about style, colors, file formats, revisions, usage

### Test Case 3: Writing
**Input:** "Write SEO articles for my blog"
**Expected:** Questions about topics, word count, tone, keywords, frequency

### Test Case 4: Marketing
**Input:** "Instagram marketing campaign"
**Expected:** Questions about goals, content type, posting frequency, duration

### Test Case 5: Video
**Input:** "Edit my YouTube travel vlogs"
**Expected:** Questions about length, style, music, transitions, thumbnail

### Test Case 6: Mixed/Unclear
**Input:** "Need help with my business"
**Expected:** Broad discovery questions to identify specific needs

---

## Restart Required

⚠️ **Backend server needs to be restarted** to load the updated AI prompts:

```bash
# In terminal 4 (backend)
Ctrl+C
uvicorn app.main:app --reload
```

---

## Next Steps

1. ✅ AI prompts updated to be universal
2. ⏳ **Restart backend server**
3. ⏳ Test with different project types:
   - Software project
   - Design project
   - Writing project
   - Marketing project
   - Video project
4. ⏳ Verify questions are relevant to each type
5. ⏳ Check budget ranges match project complexity

The AI is now ready to handle **any type of freelance project**! 🌍

