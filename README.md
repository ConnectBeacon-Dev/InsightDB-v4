## New approach

### Deployment

### Package Creation
- python .\make_wheelhouse.py
- Package will be created in wheelhouse

### Package Installation
python .\install_offline_env.py

### Running the app
python run_pipeline_and_serve.py

### If u have to run package seperately
- python.exe  -m waitress --listen=0.0.0.0:8000 app_rag_chat:app

### Before delivering to DPIT make the following changes

#### File app_rag_chat.py
- port = int(os.getenv("PORT", "8000"))  <<< Before
- port = int(os.getenv("PORT", "443"))   <<< After

#### File demo.html
      <chatbot-widget 
        api-url="http://127.0.0.1:8000"   <<< Before
    
      <chatbot-widget 
        api-url="https://schemes.ddpdashboard.gov.in/aichat"  <<< After

### File chatbot-widget

Function: connectedCallback()
- const apiUrl = this.getAttribute('api-url') || 'http://127.0.0.1:8000'; <<<before

- const apiUrl = this.getAttribute('api-url') || 'https://schemes.ddpdashboard.gov.in/aichat';  <<<< After

