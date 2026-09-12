# **Sales Cloud**

A general-purpose Claude plugin for sales teams. Ask Claude for account context, call prep, pipeline reviews, drafted outreach, and more. Powered by your own Salesforce data and intelligence.

Sales Cloud (beta) includes ready-to-use skills for account executives and sales leaders. Connect Salesforce and Slack, with optional connectors for email, calendar, productivity, and document services.

Developed by Salesforce for sales organizations, the plugin provides a practical foundation that works out of the box and can be adapted to your team’s sales process.

## **What you get**

An account executive starts with `/salesforce-for-sales:daily-briefing` to see today’s meetings with Salesforce account context, opportunities closing soon, warnings about stale activity, relevant Slack messages, and unread customer emails. Before a call, `/salesforce-for-sales:call-prep` produces a one-page brief covering attendees, account history, recent call notes, and suggested questions. After the call, `/salesforce-for-sales:call-follow-up` turns a transcript into a customer email draft and an internal Slack summary.

A sales leader uses `/salesforce-for-sales:team-pipeline` to see a team pipeline summary, the opportunities most likely to affect the quarter, recommended actions, and focused coaching questions for each account executive.

Read-only analysis respects each user’s Salesforce permissions. With a read-only connection, analysis remains available, and write steps provide guidance or explain what requires additional access.

## **Quick start**

### **1\. Install**

```
/plugin marketplace add https://github.com/salesforce/salesforce-skills/tree/claude-prod
/plugin install salesforce-for-sales
```

### **2\. Connect Salesforce**

Sales Cloud connects through Salesforce Hosted MCP using Headless 360\. A Salesforce administrator first enables the MCP service and creates an External Client App. See [SETUP.md](SETUP.md) for the one-time configuration steps.

After the administrator provides the app’s Consumer Key, add it to `.mcp.json` and select Connect. Connect Slack from the plugin configuration. For optional connectors, authenticate the corresponding services in the Connectors panel in Cowork or with `/mcp` in Claude Code.

### **3\. Try it**

```
/salesforce-for-sales:daily-briefing
```

See [SETUP.md](SETUP.md) for the complete setup walkthrough.

## **Skills**

Sales Cloud skills align with how sales teams already work in Salesforce. Ask Claude in plain language, or invoke a skill directly using / when you want a specific workflow.

Salesforce write actions require a write-capable connection. With a read-only connection, read workflows remain available, and write-dependent skills provide manual guidance when supported. See [SETUP.md](SETUP.md).

## **Design principles**

* **Use existing access; write only after approval.** Read-only skills do not create or modify Salesforce records.&nbsp;  
* **Draft before sending.** Outreach and follow-up emails are created as drafts for review rather than sent automatically.  
* **Stay grounded in records.** Skills link the Salesforce records they discuss and preserve queried values.  
* **Work with your Salesforce configuration.** Skills use the schema, field names, stages, and permissions available in your organization. Additional context such as customer profiles, qualification frameworks, competitors, and preferred writing style can be supplied through Claude instructions.  
* **Continue when optional context is unavailable.** If a transcript or optional connected service is unavailable, the skill requests the missing input or proceeds with the available Salesforce context and identifies the limitation.

## **Customizing**

Sales Cloud provides a shared foundation that teams can adapt to their sales process. You can add organization-specific context through Claude instructions and tailor individual skill files where appropriate. See [SETUP.md](SETUP.md) for configuration guidance.
