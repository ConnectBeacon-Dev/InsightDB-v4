# Setup Instructions for Chatbot Examples

## Issue: Demo Not Connecting to Server

If you're experiencing connection issues with the example files, follow these steps:

## 1. Install Flask-CORS

The server needs CORS support to allow connections from local HTML files. Install it:

```bash
pip install Flask-CORS
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## 2. Restart the Server

**Stop the current server** (press Ctrl+C in the terminal), then restart it:

```bash
python app_rag_chat.py
```

You should see output like:
```
Initializing query engine...
  Views: d:\CBDPIT\RELEASE\InsightDB-v4\views
  LLM: models/Qwen2.5-3B-Instruct-Q8_0.gguf
 Query engine ready
 * Serving Flask app 'app_rag_chat'
 * Running on http://0.0.0.0:8000
```

## 3. Test the Connection

### Option A: Test with curl (command line)
```bash
curl -X POST http://127.0.0.1:8000/ask ^
  -H "Content-Type: application/json" ^
  -d "{\"query\": \"Hello\"}"
```

Expected response:
```json
{"status":"success","answer":"Hello! How can I help you..."}
```

### Option B: Test in Browser Console
Open http://127.0.0.1:8000 in your browser, open DevTools Console (F12), and run:

```javascript
fetch('http://127.0.0.1:8000/ask', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'Hello' })
})
.then(r => r.json())
.then(data => console.log('Success:', data))
.catch(e => console.error('Error:', e));
```

## 4. Open the Examples

Now you can open the example files:

### Web Component Demo:
1. Open `examples/web-component/demo.html` in your browser
2. Try asking a question

### Iframe Examples:
1. Open `examples/iframe-embed/embed-example.html` in your browser
2. The iframes should load the chat interface

### API Clients:

**Python:**
```bash
cd examples/api-clients
python chatbot_client.py
```

**JavaScript (Node.js):**
```bash
cd examples/api-clients
node chatbot_client.js
```

## Troubleshooting

### Problem: ModuleNotFoundError: No module named 'flask_cors'

**Solution:**
```bash
pip install Flask-CORS
```

### Problem: Connection still refused

**Check:**
1. Is the server running on port 8000?
2. Can you access http://127.0.0.1:8000 in your browser?
3. Check firewall settings

**Try:**
```bash
# Check if port 8000 is in use
netstat -an | findstr :8000
```

### Problem: CORS errors in browser console

**Solution:**
- Make sure you restarted the server after installing Flask-CORS
- The app_rag_chat.py file should have the CORS configuration

### Problem: "Cannot connect to API" in demos

**Solution:**
1. Verify server is running: Open http://127.0.0.1:8000 in browser
2. Check browser console (F12) for error messages
3. Try the curl test above to verify API is working

### Problem: Slow responses

**This is normal:**
- First query initializes the model (takes time)
- Subsequent queries should be faster
- Model loading happens on first request

## Verification Checklist

- [ ] Flask-CORS installed (`pip list | findstr Flask-CORS`)
- [ ] Server restarted after installing Flask-CORS
- [ ] Server shows "Running on http://0.0.0.0:8000"
- [ ] Can access http://127.0.0.1:8000 in browser
- [ ] curl test returns JSON response
- [ ] Browser console test works
- [ ] Demo files connect successfully

## Example Queries to Try

Once connected, try these queries:

```
1. "List companies in Pune"
2. "Companies with ISO 9001 certification"
3. "Show me companies in Maharashtra"
4. "How many companies are in Bengaluru?"
5. "Address of HEG LIMITED"
```

## Need More Help?

1. Check the main documentation: `CHATBOT_USER_CONTROL_GUIDE.md`
2. Review the examples README: `examples/README.md`
3. Check server logs in the terminal for error messages
4. Verify all dependencies are installed: `pip install -r requirements.txt`

---

**Quick Fix Command:**
```bash
pip install Flask-CORS && python app_rag_chat.py
```

This installs CORS support and starts the server in one command.
