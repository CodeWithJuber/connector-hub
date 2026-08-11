use std::sync::Arc;

use rmcp::handler::server::wrapper::Parameters;
use rmcp::model::{CallToolResult, ContentBlock, ServerCapabilities, ServerInfo};
use rmcp::{ErrorData, ServiceExt, schemars, tool, tool_handler, tool_router};
use serde::Deserialize;

#[derive(Clone)]
pub struct HubMcpServer {
    dispatcher: Arc<hub_core::Dispatcher>,
    auth: Arc<hub_auth::AuthStore>,
    policy: Arc<hub_policy::Policy>,
    net: Arc<hub_net::NetClient>,
}

#[derive(Deserialize, schemars::JsonSchema)]
struct SearchParams {
    #[schemars(description = "Search query")]
    query: String,
    #[schemars(description = "Optional provider filter")]
    provider: Option<String>,
}

#[derive(Deserialize, schemars::JsonSchema)]
struct DescribeParams {
    #[schemars(description = "Operation ID (e.g. hetzner.list_servers)")]
    id: String,
}

#[derive(Deserialize, schemars::JsonSchema)]
struct CallParams {
    #[schemars(description = "Operation ID")]
    id: String,
    #[schemars(description = "Arguments as JSON object")]
    args: serde_json::Value,
    #[schemars(description = "Account identifier")]
    account: Option<String>,
    #[schemars(description = "Preview without executing")]
    dry_run: Option<bool>,
    #[schemars(description = "Confirmation token for destructive operations")]
    confirmation_token: Option<String>,
}

#[tool_router]
impl HubMcpServer {
    #[tool(
        name = "list_providers",
        description = "List all available providers and their operation counts"
    )]
    async fn list_providers(&self) -> Result<String, ErrorData> {
        let catalogue = self.dispatcher.catalogue();

        let mut providers = Vec::new();
        for name in catalogue.providers() {
            let ops = catalogue.operations_for_provider(name);
            providers.push(serde_json::json!({
                "provider": name,
                "operations": ops.len(),
                "destructive": ops.iter()
                    .filter(|o| o.mutation_class == hub_policy::MutationClass::Destructive)
                    .count(),
            }));
        }

        serde_json::to_string_pretty(&providers)
            .map_err(|e| ErrorData::internal_error(e.to_string(), None))
    }

    #[tool(
        name = "search_operations",
        description = "Search for operations by keyword across all providers"
    )]
    async fn search_operations(
        &self,
        Parameters(params): Parameters<SearchParams>,
    ) -> Result<String, ErrorData> {
        let catalogue = self.dispatcher.catalogue();

        let results = catalogue.search(&params.query, params.provider.as_deref());
        let items: Vec<_> = results
            .iter()
            .map(|op| {
                serde_json::json!({
                    "id": op.id.to_string(),
                    "provider": op.provider,
                    "summary": op.summary,
                    "mutation_class": format!("{:?}", op.mutation_class),
                })
            })
            .collect();

        serde_json::to_string_pretty(&items)
            .map_err(|e| ErrorData::internal_error(e.to_string(), None))
    }

    #[tool(
        name = "describe_operation",
        description = "Get the full schema and description of a specific operation"
    )]
    async fn describe_operation(
        &self,
        Parameters(params): Parameters<DescribeParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let catalogue = self.dispatcher.catalogue();

        let op_id = hub_core::OperationId(params.id.clone());
        match catalogue.get(&op_id) {
            Some(op) => Ok(CallToolResult::success(vec![ContentBlock::text(
                serde_json::to_string_pretty(op).unwrap(),
            )])),
            None => Ok(CallToolResult::error(vec![ContentBlock::text(format!(
                "Unknown operation: {}",
                params.id
            ))])),
        }
    }

    #[tool(
        name = "call_operation",
        description = "Execute an operation with validation and safety checks"
    )]
    async fn call_operation(
        &self,
        Parameters(params): Parameters<CallParams>,
    ) -> Result<CallToolResult, ErrorData> {
        let op_id = hub_core::OperationId(params.id.clone());

        let result = self
            .dispatcher
            .call(
                &op_id,
                params.args,
                params.account.as_deref(),
                params.dry_run.unwrap_or(false),
                params.confirmation_token.as_deref(),
                &self.policy,
                &self.auth,
                &self.net,
            )
            .await;

        match result {
            Ok(outcome) => Ok(CallToolResult::success(vec![ContentBlock::text(
                serde_json::to_string_pretty(&outcome).unwrap(),
            )])),
            Err(e) => Ok(CallToolResult::error(vec![ContentBlock::text(
                e.to_string(),
            )])),
        }
    }

    #[tool(name = "health", description = "Check the health of the connector hub")]
    async fn health(&self) -> String {
        let catalogue = self.dispatcher.catalogue();
        serde_json::json!({
            "ok": true,
            "service": "connector-hub",
            "providers": catalogue.providers().len(),
            "operations": catalogue.len(),
        })
        .to_string()
    }
}

#[tool_handler]
impl rmcp::ServerHandler for HubMcpServer {
    fn get_info(&self) -> ServerInfo {
        let mut info = ServerInfo::new(ServerCapabilities::builder().enable_tools().build());
        info.instructions = Some("Omni Connector Hub — search, describe, and execute operations across all connected providers with full safety controls.".into());
        info
    }
}

pub async fn serve() -> anyhow::Result<()> {
    tracing::info!("starting MCP stdio server");

    let catalogue = super::build_catalogue()?;
    let dispatcher = hub_core::Dispatcher::new(catalogue);

    let policy_path = std::path::Path::new("permissions.toml");
    let policy = if policy_path.exists() {
        let content = std::fs::read_to_string(policy_path)?;
        hub_policy::Policy::from_toml(&content)?
    } else {
        hub_policy::Policy::deny_all()
    };

    let server = HubMcpServer {
        dispatcher: Arc::new(dispatcher),
        auth: Arc::new(hub_auth::AuthStore::from_env()),
        policy: Arc::new(policy),
        net: Arc::new(hub_net::NetClient::new(hub_net::SsrfPolicy::default())),
    };

    let transport = rmcp::transport::io::stdio();
    let running = server.serve(transport).await?;
    tracing::info!("MCP server running on stdio");

    running.waiting().await?;
    Ok(())
}
