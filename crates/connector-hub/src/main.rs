mod mcp;

use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "connector-hub", about = "Omni Connector Hub")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// List all providers and their operation counts
    List,
    /// Search operations across all providers
    Search {
        query: String,
        #[arg(short, long)]
        provider: Option<String>,
    },
    /// Describe a specific operation's schema
    Describe { operation_id: String },
    /// Start the MCP stdio server
    Mcp,
    /// Verify the audit ledger
    AuditVerify {
        #[arg(default_value = "audit.jsonl")]
        path: String,
    },
    /// Validate the installation
    Validate,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "connector_hub=info".parse().unwrap()),
        )
        .with_writer(std::io::stderr)
        .init();

    let cli = Cli::parse();

    match cli.command {
        Command::List => {
            let catalogue = build_catalogue()?;
            for provider in catalogue.providers() {
                let ops = catalogue.operations_for_provider(provider);
                let destructive = ops
                    .iter()
                    .filter(|o| o.mutation_class == hub_policy::MutationClass::Destructive)
                    .count();
                println!(
                    "{provider:16} {total:4} operations ({destructive} destructive)",
                    total = ops.len()
                );
            }
            println!("\nTotal: {} operations", catalogue.len());
        }
        Command::Search { query, provider } => {
            let catalogue = build_catalogue()?;
            let results = catalogue.search(&query, provider.as_deref());
            if results.is_empty() {
                println!("No operations found for '{query}'");
            } else {
                for op in &results {
                    println!(
                        "{:40} {:12} {}",
                        op.id,
                        format!("{:?}", op.mutation_class),
                        op.summary
                    );
                }
                println!("\n{} results", results.len());
            }
        }
        Command::Describe { operation_id } => {
            let catalogue = build_catalogue()?;
            let id = hub_core::OperationId(operation_id);
            match catalogue.get(&id) {
                Some(op) => {
                    println!("{}", serde_json::to_string_pretty(op)?);
                }
                None => {
                    eprintln!("Unknown operation: {id}");
                    std::process::exit(1);
                }
            }
        }
        Command::Mcp => {
            mcp::serve().await?;
        }
        Command::AuditVerify { path } => {
            match hub_policy::AuditLedger::verify(std::path::Path::new(&path)) {
                Ok(count) => println!("Ledger verified: {count} entries, chain intact"),
                Err(e) => {
                    eprintln!("Ledger verification failed: {e}");
                    std::process::exit(1);
                }
            }
        }
        Command::Validate => {
            let mut errors: Vec<String> = Vec::new();
            let mut warnings: Vec<String> = Vec::new();

            println!("Validating installation...\n");

            // 1. Check specs directory
            let specs_dir = specs_dir();
            if !specs_dir.is_dir() {
                errors.push(format!(
                    "specs/ directory not found at {}",
                    specs_dir.display()
                ));
            } else {
                let mut spec_count = 0;
                for entry in std::fs::read_dir(&specs_dir)? {
                    let entry = entry?;
                    let path = entry.path();
                    if path.extension().is_some_and(|e| e == "json") {
                        let content = std::fs::read_to_string(&path)?;
                        let provider = path.file_stem().unwrap().to_string_lossy().to_string();
                        if let Err(e) = serde_json::from_str::<serde_json::Value>(&content) {
                            errors.push(format!("specs/{provider}.json: invalid JSON: {e}"));
                        } else {
                            spec_count += 1;
                        }
                    }
                }
                println!("  Specs directory: {spec_count} spec file(s) found");
            }

            // 2. Build catalogue and check for issues
            match build_catalogue() {
                Ok(catalogue) => {
                    println!(
                        "  Catalogue: {} operations across {} providers",
                        catalogue.len(),
                        catalogue.providers().len()
                    );
                    println!(
                        "  Destructive operations: {}",
                        catalogue.destructive_operations().len()
                    );

                    if catalogue.is_empty() {
                        warnings.push("catalogue is empty — no operations loaded".into());
                    }

                    // 3. Check for duplicate operation IDs (the catalogue is a
                    // HashMap so duplicates silently overwrite — detect that)
                    let mut seen_ids: std::collections::HashMap<&str, &str> =
                        std::collections::HashMap::new();
                    for op in catalogue.all_operations() {
                        if let Some(prev_provider) = seen_ids.get(op.id.0.as_str()) {
                            errors.push(format!(
                                "duplicate operation ID '{}' in providers '{}' and '{}'",
                                op.id, prev_provider, op.provider
                            ));
                        } else {
                            seen_ids.insert(&op.id.0, &op.provider);
                        }
                    }

                    // 4. Check each provider has at least one operation
                    for provider in catalogue.providers() {
                        let ops = catalogue.operations_for_provider(provider);
                        if ops.is_empty() {
                            warnings.push(format!("provider '{provider}' has no operations"));
                        }
                    }
                }
                Err(e) => {
                    errors.push(format!("failed to build catalogue: {e}"));
                }
            }

            // 5. Check auth store can find credentials (warnings only)
            let auth = hub_auth::AuthStore::from_env();
            let configured: Vec<&str> = auth.providers();
            if configured.is_empty() {
                warnings.push("no credentials configured in environment".into());
            } else {
                println!("  Credentials configured for: {}", configured.join(", "));
            }

            // 6. Check plugin manifest version parity
            let manifest_paths = [
                ".claude-plugin/plugin.json",
                ".claude-plugin/marketplace.json",
                ".codex-plugin/plugin.json",
                "kimi.plugin.json",
            ];
            let mut manifest_versions: Vec<(String, String)> = Vec::new();
            for path_str in &manifest_paths {
                let p = std::path::Path::new(path_str);
                if p.exists() {
                    match std::fs::read_to_string(p) {
                        Ok(content) => {
                            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content) {
                                if let Some(ver) = val.get("version").and_then(|v| v.as_str()) {
                                    manifest_versions.push((path_str.to_string(), ver.to_string()));
                                } else {
                                    warnings.push(format!("{path_str}: missing 'version' field"));
                                }
                            } else {
                                errors.push(format!("{path_str}: invalid JSON"));
                            }
                        }
                        Err(e) => errors.push(format!("{path_str}: {e}")),
                    }
                } else {
                    warnings.push(format!("{path_str}: not found"));
                }
            }
            if !manifest_versions.is_empty() {
                let first_ver = &manifest_versions[0].1;
                let all_match = manifest_versions.iter().all(|(_, v)| v == first_ver);
                if all_match {
                    println!(
                        "  Plugin manifests: {} file(s) at version {first_ver}",
                        manifest_versions.len()
                    );
                } else {
                    for (path, ver) in &manifest_versions {
                        errors.push(format!("manifest version mismatch: {path} = {ver}"));
                    }
                }
            }

            // 7. Check audit ledger if present
            let ledger_path = std::path::Path::new("audit.jsonl");
            if ledger_path.exists() {
                match hub_policy::AuditLedger::verify(ledger_path) {
                    Ok(count) => println!("  Audit ledger: {count} entries, chain intact"),
                    Err(e) => errors.push(format!("audit ledger verification failed: {e}")),
                }
            }

            // Report
            println!();
            if !warnings.is_empty() {
                for w in &warnings {
                    eprintln!("  WARN: {w}");
                }
            }
            if !errors.is_empty() {
                for e in &errors {
                    eprintln!("  ERROR: {e}");
                }
                eprintln!("\nValidation failed with {} error(s).", errors.len());
                std::process::exit(1);
            }

            println!("Validation passed.");
        }
    }

    Ok(())
}

/// Resolve the provider specs directory.
///
/// Resolution order:
/// 1. `CONNECTOR_HUB_SPECS_DIR` — explicit override.
/// 2. `./specs` relative to the working directory — repo-root invocation.
/// 3. `specs/` found by walking up from the executable — lets an installed
///    binary (e.g. `crates/target/release/connector-hub`) locate the specs
///    without the caller having to set a working directory. MCP hosts launch
///    servers with an arbitrary cwd, so this is the common case.
///
/// Falls back to `./specs` so callers keep a stable "not found" path to report.
fn specs_dir() -> std::path::PathBuf {
    if let Ok(dir) = std::env::var("CONNECTOR_HUB_SPECS_DIR") {
        return std::path::PathBuf::from(dir);
    }

    let cwd_specs = std::path::PathBuf::from("specs");
    if cwd_specs.is_dir() {
        return cwd_specs;
    }

    if let Ok(exe) = std::env::current_exe() {
        let mut ancestor = exe.parent();
        while let Some(dir) = ancestor {
            let candidate = dir.join("specs");
            if candidate.is_dir() {
                return candidate;
            }
            ancestor = dir.parent();
        }
    }

    cwd_specs
}

fn build_catalogue() -> anyhow::Result<hub_core::Catalogue> {
    let mut catalogue = hub_core::Catalogue::new();

    let specs_dir = specs_dir();
    if specs_dir.is_dir() {
        for entry in std::fs::read_dir(specs_dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.extension().is_some_and(|e| e == "json") {
                let content = std::fs::read_to_string(&path)?;
                let provider = path.file_stem().unwrap().to_string_lossy().to_string();

                let result = if content.contains("\"openapi\"") {
                    let spec = hub_spec::OpenApiSpec::from_json(&content, &provider)?;
                    spec.operations()?
                } else if content.contains("\"discoveryVersion\"")
                    || content.contains("\"baseUrl\"")
                {
                    let spec = hub_spec::GoogleDiscoverySpec::from_json(&content, &provider)?;
                    spec.operations()?
                } else {
                    tracing::warn!("unknown spec format: {}", path.display());
                    continue;
                };

                for raw in result {
                    catalogue.register(hub_core::Operation {
                        id: hub_core::OperationId(raw.id),
                        provider: raw.provider,
                        summary: raw.summary,
                        description: raw.description,
                        mutation_class: match raw.mutation_class.as_str() {
                            "destructive" => hub_policy::MutationClass::Destructive,
                            "mutating" => hub_policy::MutationClass::Mutating,
                            _ => hub_policy::MutationClass::ReadOnly,
                        },
                        http_method: raw.http_method,
                        path_template: raw.path,
                        parameters: hub_core::ParameterSchema {
                            json_schema: raw.parameters,
                        },
                        tags: raw.tags,
                        transport: hub_core::Transport::Http,
                    });
                }

                tracing::info!(
                    "loaded {} spec: {} operations",
                    provider,
                    catalogue.operations_for_provider(&provider).len()
                );
            }
        }
    }

    register_email_operations(&mut catalogue);
    register_ops_operations(&mut catalogue);

    Ok(catalogue)
}

fn register_email_operations(catalogue: &mut hub_core::Catalogue) {
    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("email.send_email".into()),
        provider: "email".into(),
        summary: "Send an email via SMTP".into(),
        description: "Send an email message using the configured SMTP transport.".into(),
        mutation_class: hub_policy::MutationClass::Mutating,
        http_method: "POST".into(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["to", "subject"],
                "properties": {
                    "to": {"description": "Recipient email address(es)", "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
                    "cc": {"description": "CC recipients", "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
                    "bcc": {"description": "BCC recipients", "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Plain text body"},
                    "body_html": {"type": "string", "description": "HTML body"},
                    "from": {"type": "string", "description": "Override sender address"}
                }
            }),
        },
        tags: vec!["email".into(), "smtp".into()],
        transport: hub_core::Transport::Smtp,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("email.list_accounts".into()),
        provider: "email".into(),
        summary: "List configured email accounts".into(),
        description: "List all IMAP/SMTP email accounts configured via environment variables."
            .into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({"type": "object"}),
        },
        tags: vec!["email".into(), "imap".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("email.check_inbox".into()),
        provider: "email".into(),
        summary: "Check inbox for new messages".into(),
        description: "Connect via IMAP and retrieve recent messages from the inbox.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "account": {"type": "string", "description": "Account label (default: first configured)"},
                    "limit": {"type": "integer", "description": "Max messages to return", "default": 10},
                    "folder": {"type": "string", "description": "IMAP folder", "default": "INBOX"}
                }
            }),
        },
        tags: vec!["email".into(), "imap".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("email.search".into()),
        provider: "email".into(),
        summary: "Search emails via IMAP".into(),
        description: "Search for emails matching criteria using IMAP SEARCH.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "IMAP search query"},
                    "account": {"type": "string", "description": "Account label"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20},
                    "folder": {"type": "string", "description": "IMAP folder", "default": "INBOX"}
                }
            }),
        },
        tags: vec!["email".into(), "imap".into()],
        transport: hub_core::Transport::Local,
    });
}

fn register_ops_operations(catalogue: &mut hub_core::Catalogue) {
    // ops_ssh: 3 actions
    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_ssh.run_local".into()),
        provider: "ops_ssh".into(),
        summary: "Run a command on the local host".into(),
        description: "Execute a shell command locally with configurable timeout.".into(),
        mutation_class: hub_policy::MutationClass::Destructive,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
                }
            }),
        },
        tags: vec!["ops".into(), "ssh".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_ssh.run_ssh".into()),
        provider: "ops_ssh".into(),
        summary: "Run a command on a remote host via SSH".into(),
        description: "Execute a command on a remote host using SSH key authentication.".into(),
        mutation_class: hub_policy::MutationClass::Destructive,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["host", "command"],
                "properties": {
                    "host": {"type": "string", "description": "SSH host (from SSH_HOSTS or user@host)"},
                    "command": {"type": "string", "description": "Command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
                }
            }),
        },
        tags: vec!["ops".into(), "ssh".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_ssh.list_hosts".into()),
        provider: "ops_ssh".into(),
        summary: "List configured SSH hosts".into(),
        description: "List the hosts configured in the SSH_HOSTS environment variable.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({"type": "object"}),
        },
        tags: vec!["ops".into(), "ssh".into()],
        transport: hub_core::Transport::Local,
    });

    // ops_browser: 3 actions
    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_browser.fetch".into()),
        provider: "ops_browser".into(),
        summary: "Fetch a URL and return its content".into(),
        description: "HTTP GET a URL with SSRF protection and return the response body.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "method": {"type": "string", "description": "HTTP method", "default": "GET"},
                    "max_bytes": {"type": "integer", "description": "Max response size", "default": 2000000}
                }
            }),
        },
        tags: vec!["ops".into(), "browser".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_browser.check_status".into()),
        provider: "ops_browser".into(),
        summary: "Check HTTP status of a URL".into(),
        description: "Perform a HEAD request and return the HTTP status code and headers.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {"type": "string", "description": "URL to check"}
                }
            }),
        },
        tags: vec!["ops".into(), "browser".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_browser.screenshot".into()),
        provider: "ops_browser".into(),
        summary: "Take a screenshot of a URL".into(),
        description: "Capture a screenshot of a web page (stub — requires headless browser)."
            .into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {"type": "string", "description": "URL to capture"},
                    "width": {"type": "integer", "description": "Viewport width", "default": 1280},
                    "height": {"type": "integer", "description": "Viewport height", "default": 720}
                }
            }),
        },
        tags: vec!["ops".into(), "browser".into()],
        transport: hub_core::Transport::Local,
    });

    // ops_security: 5 actions
    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_security.audit_password_strength".into()),
        provider: "ops_security".into(),
        summary: "Audit password strength".into(),
        description: "Evaluate a password against common strength criteria.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["password"],
                "properties": {
                    "password": {"type": "string", "description": "Password to audit"}
                }
            }),
        },
        tags: vec!["ops".into(), "security".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_security.check_ssl".into()),
        provider: "ops_security".into(),
        summary: "Check SSL certificate for a domain".into(),
        description: "Connect to a host and inspect its TLS certificate for validity and expiry."
            .into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["host"],
                "properties": {
                    "host": {"type": "string", "description": "Hostname to check"},
                    "port": {"type": "integer", "description": "Port", "default": 443}
                }
            }),
        },
        tags: vec!["ops".into(), "security".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_security.scan_common_exposure".into()),
        provider: "ops_security".into(),
        summary: "Scan for common exposure paths".into(),
        description: "Check a target for commonly exposed files and directories.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {"type": "string", "description": "Base URL to scan"}
                }
            }),
        },
        tags: vec!["ops".into(), "security".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_security.ssh_config_audit".into()),
        provider: "ops_security".into(),
        summary: "Audit SSH server configuration".into(),
        description: "Connect to an SSH server and audit its configuration for security issues."
            .into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["host"],
                "properties": {
                    "host": {"type": "string", "description": "SSH host to audit"},
                    "port": {"type": "integer", "description": "SSH port", "default": 22}
                }
            }),
        },
        tags: vec!["ops".into(), "security".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_security.generate_secret".into()),
        provider: "ops_security".into(),
        summary: "Generate a cryptographic secret".into(),
        description: "Generate a random secret string of specified length and charset.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "length": {"type": "integer", "description": "Secret length", "default": 32},
                    "charset": {"type": "string", "description": "Character set: alphanumeric, hex, base64, ascii", "default": "alphanumeric"}
                }
            }),
        },
        tags: vec!["ops".into(), "security".into()],
        transport: hub_core::Transport::Local,
    });

    // ops_network: 5 actions
    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_network.ping".into()),
        provider: "ops_network".into(),
        summary: "Ping a host".into(),
        description: "Send ICMP pings to a host and report latency.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["host"],
                "properties": {
                    "host": {"type": "string", "description": "Host to ping"},
                    "count": {"type": "integer", "description": "Number of pings", "default": 4}
                }
            }),
        },
        tags: vec!["ops".into(), "network".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_network.dns_lookup".into()),
        provider: "ops_network".into(),
        summary: "DNS lookup".into(),
        description: "Resolve DNS records for a domain.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["domain"],
                "properties": {
                    "domain": {"type": "string", "description": "Domain to look up"},
                    "record_type": {"type": "string", "description": "Record type (A, AAAA, MX, etc.)", "default": "A"}
                }
            }),
        },
        tags: vec!["ops".into(), "network".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_network.port_check".into()),
        provider: "ops_network".into(),
        summary: "Check if a port is open".into(),
        description: "Test TCP connectivity to a host on a specific port.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["host", "port"],
                "properties": {
                    "host": {"type": "string", "description": "Host to check"},
                    "port": {"type": "integer", "description": "Port to check"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 5}
                }
            }),
        },
        tags: vec!["ops".into(), "network".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_network.traceroute".into()),
        provider: "ops_network".into(),
        summary: "Traceroute to a host".into(),
        description: "Trace the network path to a destination host.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["host"],
                "properties": {
                    "host": {"type": "string", "description": "Destination host"},
                    "max_hops": {"type": "integer", "description": "Maximum number of hops", "default": 30}
                }
            }),
        },
        tags: vec!["ops".into(), "network".into()],
        transport: hub_core::Transport::Local,
    });

    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("ops_network.http_headers".into()),
        provider: "ops_network".into(),
        summary: "Inspect HTTP response headers".into(),
        description: "Send an HTTP request and return response headers for analysis.".into(),
        mutation_class: hub_policy::MutationClass::ReadOnly,
        http_method: String::new(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {"type": "string", "description": "URL to inspect"},
                    "method": {"type": "string", "description": "HTTP method", "default": "HEAD"}
                }
            }),
        },
        tags: vec!["ops".into(), "network".into()],
        transport: hub_core::Transport::Local,
    });
}
