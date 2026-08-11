use std::collections::HashMap;

use crate::catalogue::Catalogue;
use crate::operation::{MutationClass, OperationId};
use crate::result::{ExecutionOutcome, OperationError};

pub struct Dispatcher {
    catalogue: Catalogue,
}

impl Dispatcher {
    pub fn new(catalogue: Catalogue) -> Self {
        Self { catalogue }
    }

    pub fn catalogue(&self) -> &Catalogue {
        &self.catalogue
    }

    #[allow(clippy::too_many_arguments)]
    pub async fn call(
        &self,
        id: &OperationId,
        args: serde_json::Value,
        account: Option<&str>,
        dry_run: bool,
        confirmation_token: Option<&str>,
        policy: &hub_policy::Policy,
        auth: &hub_auth::AuthStore,
        net: &hub_net::NetClient,
    ) -> Result<ExecutionOutcome, OperationError> {
        let op = self
            .catalogue
            .get(id)
            .ok_or_else(|| OperationError::UnknownOperation(id.to_string()))?;

        let _grant = policy.check(&op.provider, account, &op.id.0, op.mutation_class)?;

        if dry_run {
            return Ok(ExecutionOutcome::DryRun {
                would_execute: op.summary.clone(),
                mutation_class: format!("{:?}", op.mutation_class),
            });
        }

        if op.mutation_class == MutationClass::Destructive {
            let expected = format!("CONFIRM:{}:{}", op.provider, op.id.method());
            match confirmation_token {
                Some(token) if token == expected => {}
                _ if _grant.standing_approval => {}
                _ => {
                    return Ok(ExecutionOutcome::ConfirmationRequired {
                        provider: op.provider.clone(),
                        operation: op.id.to_string(),
                        token_format: expected,
                    });
                }
            }
        }

        let credential = auth.get(&op.provider, account)?;

        let base_url = credential.base_url.as_deref().unwrap_or("");
        let url = format!("{}{}", base_url.trim_end_matches('/'), &op.path_template);

        let mut headers = HashMap::new();
        match &credential.auth {
            hub_auth::credential::AuthMethod::Bearer { token } => {
                headers.insert("Authorization".into(), format!("Bearer {token}"));
            }
            hub_auth::credential::AuthMethod::Header { name, value } => {
                headers.insert(name.clone(), value.clone());
            }
            hub_auth::credential::AuthMethod::Basic { username, password } => {
                use std::io::Write;
                let mut buf = Vec::new();
                write!(buf, "{username}:{password}").unwrap();
                let encoded = base64_encode(&buf);
                headers.insert("Authorization".into(), format!("Basic {encoded}"));
            }
            _ => {}
        }

        let response = net
            .execute(&op.http_method, &url, &args, &headers, &op.provider)
            .await?;

        Ok(ExecutionOutcome::Succeeded {
            executed: true,
            data: response,
        })
    }
}

fn base64_encode(input: &[u8]) -> String {
    const CHARS: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut result = String::new();
    for chunk in input.chunks(3) {
        let b0 = chunk[0] as u32;
        let b1 = chunk.get(1).copied().unwrap_or(0) as u32;
        let b2 = chunk.get(2).copied().unwrap_or(0) as u32;
        let triple = (b0 << 16) | (b1 << 8) | b2;
        result.push(CHARS[((triple >> 18) & 0x3F) as usize] as char);
        result.push(CHARS[((triple >> 12) & 0x3F) as usize] as char);
        if chunk.len() > 1 {
            result.push(CHARS[((triple >> 6) & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
        if chunk.len() > 2 {
            result.push(CHARS[(triple & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
    }
    result
}
