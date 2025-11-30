import gradio as gr

def get_readme_content():
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "# iOS MCP Server\n\nWelcome! This tool is designed to run locally with a physical iOS device connected."

with gr.Blocks() as demo:
    gr.Markdown(
        """
        # 📱 iOS MCP Server
        
        **Connect your iPhone to Claude/LLMs for advanced photos querying using Photos Metadata and management.**
        
        > ⚠️ **NOTE:** This Space is a demo/landing page. The actual MCP server requires a physical USB connection to an iOS device and must be run locally on your machine (macOS/Linux).
        """
    )
    
    with gr.Tab("📺 Demo & Features"):
        gr.Markdown("### See it in action")
        # Placeholder for video - User needs to replace this or upload a video to the repo
        gr.HTML(
            """
            <div style="display: flex; justify-content: center; align-items: center; width: 100%; margin-bottom: 20px;">
                <iframe 
                    src="https://drive.google.com/file/d/1yyqCKYXskhf4JLdMTkgvbPJ6gCqacOG3/preview" 
                    width="640" 
                    height="480" 
                    allow="autoplay"
                    style="border: none; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                </iframe>
            </div>
            <p style="text-align: center; color: #666; font-size: 0.9em;">
            </p>
            """
        )
        gr.Markdown(
            """
            ### Key Features
            - **Natural Language Search**: "Find photos with faces from last week"
            - **Advanced Analytics**: Grouping, Aggregation Pipelines, and SQL-like querying.
            - **Metadata Filtering**: Query by ISO, Model, Location, etc.
            - **Privacy First**: PII masking and local processing.
            - **Fast Indexing**: Incremental scanning with local DB caching.
            """
        )

    with gr.Tab("🚀 How to Run Locally"):
        gr.Markdown(
            """
            ### 1. Installation
            ```bash
            git clone https://github.com/harshaneigapula/ios_mcp
            cd ios_mcp
            pip install -r requirements.txt
            ```
            
            ### 2. Prerequisites
            - macOS or Linux
            - `libimobiledevice` installed (e.g., `brew install libimobiledevice`)
            - An unlocked iOS device connected via USB
            
            ### 3. Run the Server
            ```bash
            mcp run src/server.py
            ```
            
            ### 4. Connect to Claude
            Add to your `claude_desktop_config.json`:
            ```json
            {
              "mcpServers": {
                "ios-mcp": {
                  "command": "python",
                  "args": ["/absolute/path/to/ios_mcp/src/server.py"]
                }
              }
}
            ```
            """
        )
        
    with gr.Tab("📄 Documentation"):
        gr.Markdown(get_readme_content())

if __name__ == "__main__":
    demo.launch()
