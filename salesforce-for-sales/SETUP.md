# **Sales Cloud Setup Guide**

For full setup instructions, see [What Is Salesforce in Claude](https://help.salesforce.com/s/articleView?id=sales.what_is_salesforce_in_claude.htm&type=5).

### **Admin setup**

1. Activate the Salesforce MCP Server in Setup.  
2. Create a permission set for the users who should have access (optional but recommended).  
3. Create and configure the External Client App (ECA) to connect Claude to your org through OAuth.  
4. Connect Claude to Salesforce MCP.  
5. Set tool restrictions to keep the beta read-only.  
6. Roll out the plugin.

### **End user setup**

1. Ensure Sales Cloud Plugin is enabled&nbsp;  
2. Sign in to the Salesforce Connector

&nbsp;

### **Considerations**

**Connect Slack and optional services**

Slack is the only non-Salesforce connector declared in the bundled .mcp.json. Connect it from the plugin or Claude connector settings if you want relevant internal context and Slack summary drafts.

Other email, calendar, productivity app, and drive connectors are not declared in this package. Connect them separately in Claude only when you want those optional sources. Core Salesforce workflows will continue with the Salesforce context available to the signed-in user regardless of additional Connector status.

&nbsp;

**Slack channel guidance**

When a skill needs a Slack channel, it can ask which channel to use. You can also define channel guidance in Claude instructions, including where to prepare:

* Internal deal-summary drafts  
* Lead-handoff drafts  
* Win-announcement drafts

Slack content should remain a draft until the user explicitly approves the exact message and destination.
