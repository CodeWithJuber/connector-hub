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
            let specs_dir = std::path::Path::new("specs");
            if !specs_dir.exists() {
                errors.push("specs/ directory not found".into());
            } else {
                let mut spec_count = 0;
                for entry in std::fs::read_dir(specs_dir)? {
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

            // 6. Check audit ledger if present
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

fn build_catalogue() -> anyhow::Result<hub_core::Catalogue> {
    let mut catalogue = hub_core::Catalogue::new();

    let specs_dir = std::path::Path::new("specs");
    if specs_dir.exists() {
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

    Ok(catalogue)
}

fn register_email_operations(catalogue: &mut hub_core::Catalogue) {
    catalogue.register(hub_core::Operation {
        id: hub_core::OperationId("email.send".into()),
        provider: "email".into(),
        summary: "Send an email via SMTP".into(),
        description: "Send an email message using the configured SMTP transport. Supports plain text, HTML, and multipart bodies. Requires SMTP credentials configured via EMAIL_SMTP_* environment variables.".into(),
        mutation_class: hub_policy::MutationClass::Mutating,
        http_method: "POST".into(),
        path_template: String::new(),
        parameters: hub_core::ParameterSchema {
            json_schema: serde_json::json!({
                "type": "object",
                "required": ["to", "subject"],
                "properties": {
                    "to": {
                        "description": "Recipient email address(es). String or array of strings.",
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}}
                        ]
                    },
                    "cc": {
                        "description": "CC recipients",
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}}
                        ]
                    },
                    "bcc": {
                        "description": "BCC recipients",
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}}
                        ]
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "body": {
                        "type": "string",
                        "description": "Plain text body"
                    },
                    "body_html": {
                        "type": "string",
                        "description": "HTML body (sent as multipart/alternative with plain text)"
                    },
                    "from": {
                        "type": "string",
                        "description": "Override sender address (defaults to configured from_address)"
                    }
                }
            }),
        },
        tags: vec!["email".into(), "smtp".into()],
        transport: hub_core::Transport::Smtp,
    });
}
