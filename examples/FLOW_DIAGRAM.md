# Complete Flow: demo.html → app_rag_chat.py

This document explains the complete data flow from when a user opens `demo.html` to receiving an AI response.

---

## 📊 Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION                         │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. User opens demo.html in browser                              │
│    File: examples/web-component/demo.html                       │
│    Protocol: file:/// (local file system)                       │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Browser loads and parses HTML                                │
│    - Loads CSS styles                                           │
│    - Finds <script src="chatbot-widget.js">                     │
│    - Loads JavaScript file                                      │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. chatbot-widget.js initializes                                │
│    File: examples/web-component/chatbot-widget.js               │
│                                                                  │
│    class ChatbotWidget extends HTMLElement {                    │
│      connectedCallback() {                                      │
│        const apiUrl = 'http://127.0.0.1:8000'  ← Gets API URL   │
│        this.render(apiUrl, theme, height)      ← Builds UI      │
│        this.setupEventListeners()              ← Adds handlers  │
│      }                                                           │
│    }                                                             │
│                                                                  │
│    customElements.define('chatbot-widget', ChatbotWidget)       │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Web Component renders in browser                             │
│    - Creates Shadow DOM                                         │
│    - Injects CSS styles                                         │
│    - Renders chat interface:                                    │
│      • Header with "DPIT Chatbot"                               │
│      • Messages container                                       │
│      • Input textarea                                           │
│      • Send button                                              │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. User types message and clicks Send                           │
│    Example: "List companies in Pune"                            │
│                                                                  │
│    Event: sendButton.addEventListener('click', ...)             │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. JavaScript prepares HTTP request                             │
│    Function: async sendMessage()                                │
│                                                                  │
│    const response = await fetch(                                │
│      'http://127.0.0.1:8000/ask_stream',                        │
│      {                                                           │
│        method: 'POST',                                           │
│        headers: { 'Content-Type': 'application/json' },         │
│        body: JSON.stringify({                                   │
│          query: "List companies in Pune",                       │
│          k: 20                                                   │
│        })                                                        │
│      }                                                           │
│    )                                                             │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│              HTTP REQUEST OVER NETWORK                           │
│                                                                  │
│    POST /ask_stream HTTP/1.1                                    │
│    Host: 127.0.0.1:8000                                         │
│    Content-Type: application/json                               │
│    Origin: null                                                 │
│                                                                  │
│    Body:                                                         │
│    {                                                             │
│      "query": "List companies in Pune",                         │
│      "k": 20                                                     │
│    }                                                             │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. Flask server receives request                                │
│    File: app_rag_chat.py                                        │
│    Port: 8000                                                    │
│                                                                  │
│    @app.post("/ask_stream")                                     │
│    def ask_stream():                                            │
│      data = request.get_json()  ← Parses JSON body             │
│      q = data.get("query")      ← Gets query string            │
│      k = data.get("k")          ← Gets k parameter             │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. CORS middleware adds headers                                 │
│    Module: flask_cors                                           │
│                                                                  │
│    CORS(app, resources={                                        │
│      r"/*": {                                                    │
│        "origins": "*",  ← Allows all origins (including file://)│
│        "methods": ["GET", "POST", "OPTIONS"],                   │
│        "allow_headers": ["Content-Type"]                        │
│      }                                                           │
│    })                                                            │
│                                                                  │
│    Response headers added:                                      │
│    • Access-Control-Allow-Origin: *                             │
│    • Access-Control-Allow-Methods: POST, OPTIONS                │
│    • Access-Control-Allow-Headers: Content-Type                 │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 9. Check for smalltalk/off-topic                                │
│    Function: _smalltalk_or_offtopic(q)                          │
│                                                                  │
│    if _GREET_RE.search(q):      ← Checks for greetings         │
│      return "Hello! How can..."                                 │
│    if _OFFTOPIC_RE.search(q):   ← Checks for off-topic         │
│      return "I'm focused on..."                                 │
│                                                                  │
│    If matches: Stream quick reply and skip query engine         │
│    If no match: Continue to query engine                        │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 10. Call query engine                                           │
│     Function: _run_query(q, k)                                  │
│                                                                  │
│     engine = get_query_engine()  ← Gets singleton instance      │
│     response = engine.natural_language_query(                   │
│       question="List companies in Pune",                        │
│       top_k=20                                                   │
│     )                                                            │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 11. Query engine processes request                              │
│     File: engine/full_engine_query.py                           │
│     Class: EnhancedQueryEngine                                  │
│                                                                  │
│     Steps:                                                       │
│     a) Classify intent (location query, certification, etc.)    │
│     b) Generate semantic embedding of query                     │
│     c) Search semantic index for relevant chunks                │
│     d) Retrieve top_k results from views (pandas DataFrames)    │
│     e) Format context for LLM                                   │
│     f) Generate natural language answer using LLM               │
│                                                                  │
│     Returns:                                                     │
│     {                                                            │
│       "answer": "Based on the data, here are companies...",     │
│       "results": [...],                                         │
│       "count": 45                                               │
│     }                                                            │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 12. Format answer for streaming                                 │
│     Function: _format_answer(response)                          │
│                                                                  │
│     answer = response.get("answer")                             │
│     return answer  ← Just the answer text                       │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 13. Stream response as Server-Sent Events (SSE)                 │
│     Function: generate() inside ask_stream()                    │
│                                                                  │
│     def generate():                                             │
│       ans = _format_answer(response)                            │
│       CHUNK = 200  ← Split into 200-char chunks                 │
│                                                                  │
│       for i in range(0, len(ans), CHUNK):                       │
│         chunk_text = ans[i:i+CHUNK]                             │
│         yield f"event: token\n"                                 │
│         yield f"data: {json.dumps(chunk_text)}\n\n"             │
│         time.sleep(0.02)  ← Small delay for smooth UI           │
│                                                                  │
│       yield "event: done\ndata: {}\n\n"                         │
│                                                                  │
│     return Response(generate(),                                 │
│                    mimetype="text/event-stream")                │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│         HTTP RESPONSE STREAMS BACK TO BROWSER                    │
│                                                                  │
│    HTTP/1.1 200 OK                                              │
│    Content-Type: text/event-stream                              │
│    Access-Control-Allow-Origin: *                               │
│    Cache-Control: no-cache                                      │
│                                                                  │
│    event: token                                                 │
│    data: "Based on the available data, here are "              │
│                                                                  │
│    event: token                                                 │
│    data: "some companies in Pune:\n\n1. ABC "                  │
│                                                                  │
│    event: token                                                 │
│    data: "PRIVATE LIMITED - Address: ..."                      │
│                                                                  │
│    ...more chunks...                                            │
│                                                                  │
│    event: done                                                  │
│    data: {}                                                     │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 14. Browser receives SSE stream                                 │
│     JavaScript: response.body.getReader()                       │
│                                                                  │
│     const reader = response.body.getReader()                    │
│     const decoder = new TextDecoder()                           │
│     let buffer = ''                                             │
│                                                                  │
│     while (true) {                                              │
│       const { value, done } = await reader.read()               │
│       if (done) break                                           │
│                                                                  │
│       buffer += decoder.decode(value, {stream: true})           │
│       // Parse SSE events separated by \n\n                     │
│     }                                                            │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 15. Parse SSE events                                            │
│                                                                  │
│     for each event:                                             │
│       if eventType === 'token':                                 │
│         • Remove typing indicator (first time)                  │
│         • Create answer bubble (first time)                     │
│         • Append token to answer                                │
│         • Update bubble.textContent                             │
│         • Auto-scroll to bottom                                 │
│                                                                  │
│       if eventType === 'done':                                  │
│         • Stop reading stream                                   │
│         • Enable send button                                    │
│         • Focus input                                           │
│                                                                  │
│       if eventType === 'error':                                 │
│         • Display error message                                 │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ 16. UI updates in real-time                                     │
│                                                                  │
│     Shadow DOM updates:                                         │
│     ┌────────────────────────────────┐                          │
│     │ DPIT Chatbot    [New Chat]    │  ← Header                │
│     ├────────────────────────────────┤                          │
│     │                                │                          │
│     │  U: List companies in Pune     │  ← User message         │
│     │                                │                          │
│     │  AI: Based on the available    │  ← AI response          │
│     │      data, here are some       │     (streaming)         │
│     │      companies in Pune:        │                          │
│     │                                │                          │
│     │      1. ABC PRIVATE LIMITED    │                          │
│     │         Address: ...           │                          │
│     │                                │                          │
│     ├────────────────────────────────┤                          │
│     │ [____________] [Send]          │  ← Input                │
│     └────────────────────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                      USER SEES RESULT                            │
│                   Flow complete! ✅                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Detailed Component Breakdown

### Frontend (Browser)

#### 1. **demo.html**
```html
<chatbot-widget 
  api-url="http://127.0.0.1:8000"
  theme="#12a150"
  height="500px"
></chatbot-widget>
<script src="chatbot-widget.js"></script>
```
**Role**: Entry point, loads the web component

#### 2. **chatbot-widget.js**
**Key Functions**:
- `connectedCallback()`: Initializes component
- `render()`: Creates UI with Shadow DOM
- `setupEventListeners()`: Binds click/keyboard events
- `sendMessage()`: Makes HTTP request, handles streaming
- `addMessage()`: Adds messages to UI

**Data Flow**:
```javascript
User clicks Send
  → sendMessage() called
    → fetch(api_url + '/ask_stream', {POST body})
      → Process SSE stream
        → Update UI in real-time
```

### Backend (Python)

#### 3. **app_rag_chat.py**
**Key Components**:

**A. Flask App Setup**
```python
app = Flask(__name__)
CORS(app, resources={"/*": {"origins": "*"}})
```

**B. Route Handler**
```python
@app.post("/ask_stream")
def ask_stream():
    data = request.get_json()
    q = data.get("query")
    k = data.get("k")
    
    # Check smalltalk
    st = _smalltalk_or_offtopic(q)
    if st:
        return Response(_stream_smalltalk(st), 
                       mimetype="text/event-stream")
    
    # Process with query engine
    def generate():
        response = _run_query(q, k)
        ans = _format_answer(response)
        # Stream in chunks
        for chunk in chunks(ans, 200):
            yield sse_token(chunk)
        yield "event: done\ndata: {}\n\n"
    
    return Response(generate(), 
                   mimetype="text/event-stream")
```

**C. Query Processing**
```python
def _run_query(question, k):
    engine = get_query_engine()
    response = engine.natural_language_query(question, top_k=k)
    return response
```

#### 4. **engine/full_engine_query.py**
**Key Functions**:
- `natural_language_query()`: Main entry point
- `build_semantic_index()`: Creates vector index
- `_classify_intent()`: Determines query type
- `_semantic_search()`: Finds relevant chunks
- `_generate_answer()`: Calls LLM for answer

**Process**:
```
Query → Intent Classification → Semantic Search → 
Data Retrieval → LLM Generation → Formatted Answer
```

---

## 🔗 Key Technologies

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Web Components | Reusable UI element |
| | Shadow DOM | Encapsulated styling |
| | Fetch API | HTTP requests |
| | Server-Sent Events | Streaming responses |
| **Backend** | Flask | Web framework |
| | Flask-CORS | Cross-origin support |
| | SSE | Streaming protocol |
| **AI** | Sentence Transformers | Embeddings |
| | LLM (Qwen) | Answer generation |
| | Pandas | Data manipulation |

---

## 📡 Network Layer Details

### Request Format
```http
POST /ask_stream HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json
Origin: null

{"query": "List companies in Pune", "k": 20}
```

### Response Format (SSE)
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Access-Control-Allow-Origin: *
Cache-Control: no-cache
Connection: keep-alive

event: token
data: "Based on "

event: token
data: "the data..."

event: done
data: {}
```

---

## 🐛 Debug Points

If something breaks, check these points in order:

1. **Browser console** (F12) - JavaScript errors
2. **Network tab** (F12) - HTTP requests/responses
3. **Server terminal** - Python errors
4. **CORS headers** - Run `python test_server_cors.py`
5. **Query engine** - Check logs in `query_log.jsonl`

---

## 🎯 Performance Notes

- **First query**: 3-5 seconds (model loading)
- **Subsequent queries**: 1-2 seconds
- **Streaming**: Updates every 200 chars (0.02s delay)
- **Memory**: ~2GB for LLM model

---

## 🔄 Complete Round Trip Time

```
User clicks Send → 0ms
JavaScript prepares request → 1-2ms
Network transmission → 1-5ms
Flask receives → <1ms
CORS processing → <1ms
Intent classification → 10-50ms
Semantic search → 100-200ms
LLM generation → 1000-3000ms (first) / 500-1000ms (cached)
Response streaming → 200-500ms
UI updates → 10-20ms per chunk
─────────────────────────────
Total: ~2-5 seconds typical
```

---

This flow represents the complete journey from user interaction to AI response!
