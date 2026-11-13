# Salesforce Plugins for Grok Bot and Cursor

Salesforce plugins for Grok Bot and Cursor. They ground your AI agent on your Salesforce org through the Headless 360 MCP server, so it can work with your org's data, schema, and workflows.

This repository is a plugin marketplace in the [Cursor plugin format](https://cursor.com/docs/plugins). Grok Bot uses the same team marketplace, so one setup covers both.

## Plugins

| Plugin                                                    | Description                                                                                                                                                                                      |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **[salesforce-for-sales](plugins/salesforce-for-sales/)** | The full Salesforce sales suite for Grok Bot and Cursor: pipeline, deals, accounts, prospecting, and daily productivity, grounded live on your org's schema through the Headless 360 MCP server. |

## Install in Grok Bot

Setup takes three people, in this order:

| Who | What |
|-----|------|
| Salesforce admin | Turns on Headless 360 and creates an External Client App |
| Cursor team admin | Adds this marketplace and configures the plugin |
| Each Grok Bot user | Connects the plugin and signs in to Salesforce |

### 1. Salesforce admin: prepare the org

1. Turn on the Headless 360 MCP server in your org.
2. Create an External Client App for Grok Bot and Cursor.
3. Give the Consumer Key and Consumer Secret to your Cursor team admin.

The [plugin README](plugins/salesforce-for-sales/README.md#admin-setup) lists the exact callback URLs, OAuth scopes, and policy settings.

### 2. Cursor team admin: add the marketplace

You need a Cursor Teams or Enterprise plan and the admin role.

1. Open the [Cursor dashboard](https://cursor.com/dashboard) and go to **Plugins & MCPs**.
2. Under **Team Marketplaces**, select **Add Marketplace**, then **Import from Repo**.
3. Paste the URL of this repository's `grok-alpha` branch:

   ```
   https://github.com/salesforce/salesforce-skills/tree/grok-alpha
   ```

4. Review the plugins and select **Add to Marketplace**.
5. Optional: in **Marketplace Settings**, turn on **Enable Auto Refresh** to pick up new releases. Otherwise select **Refresh** after each release.
6. On **Salesforce for Sales**, select **Configure** and enter:

   | Field | Value |
   |-------|-------|
   | Salesforce MCP URL | Production: `https://api.salesforce.com/platform/mcp/v1/platform/headless-360`<br>Sandbox: `https://api.salesforce.com/platform/mcp/v1/sandbox/platform/headless-360` |
   | Consumer Key | From your Salesforce admin |
   | Consumer Secret | From your Salesforce admin |

7. Make sure the plugin is enabled for the people who need it.

One configured entry points at one Salesforce org.

### 3. Grok Bot user: connect and sign in

1. In Grok Bot, open **Connect apps** from the sidebar. On mobile, select your avatar, then **Connect apps**.
2. Find **Salesforce for Sales** and add it.
3. Select **Authorize** and sign in to Salesforce.

The plugin shows as **Added** before you sign in. If it says **Needs auth** or **Disconnected**, select **Authorize** or **Reconnect**.

Your connection belongs to your account and applies to all of your Bots.

## Use in Cursor

After a team admin finishes step 2, the plugin is available in Cursor too. If it isn't installed automatically, open **Customize** in the sidebar and select **Install** on **Salesforce for Sales**. Sign in to Salesforce when Cursor prompts you.

## Troubleshooting

See [Troubleshooting](plugins/salesforce-for-sales/README.md#troubleshooting) in the plugin README.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). This project is not accepting pull requests at this moment.

## Security

See [SECURITY.md](SECURITY.md) to report a security issue.

## License

Apache License 2.0. See [LICENSE.txt](LICENSE.txt).

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
