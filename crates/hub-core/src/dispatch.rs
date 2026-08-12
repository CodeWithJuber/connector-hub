use crate::catalogue::Catalogue;
use crate::operation::{MutationClass, OperationId, Transport};
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

        match op.transport {
            Transport::Smtp => {
                return self.execute_smtp(auth, account, args).await;
            }
            Transport::Local => {
                return Ok(ExecutionOutcome::ConfigurationRequired {
                    provider: op.provider.clone(),
                    missing: vec![format!("local runtime required for operation {}", op.id)],
                });
            }
            Transport::Http => {}
        }

        let resolved = auth.resolve(&op.provider, account).await?;

        let mut args = args;
        let path = substitute_path_params(&op.path_template, &mut args);

        let url = if path.starts_with("http://") || path.starts_with("https://") {
            path
        } else {
            format!("{}{}", resolved.base_url.trim_end_matches('/'), path)
        };

        let response = net
            .execute(
                &op.http_method,
                &url,
                &args,
                &resolved.headers,
                &op.provider,
            )
            .await?;

        Ok(ExecutionOutcome::Succeeded {
            executed: true,
            data: response,
        })
    }

    async fn execute_smtp(
        &self,
        auth: &hub_auth::AuthStore,
        account: Option<&str>,
        args: serde_json::Value,
    ) -> Result<ExecutionOutcome, OperationError> {
        let cred = auth.get("email", account)?;

        let (host, port, username, password, tls, from_address) = match &cred.auth {
            hub_auth::credential::AuthMethod::Smtp {
                host,
                port,
                username,
                password,
                tls,
                from_address,
            } => (
                host.clone(),
                *port,
                username.clone(),
                password.clone(),
                *tls,
                from_address.clone(),
            ),
            _ => {
                return Err(OperationError::InvalidArguments(
                    "email provider requires SMTP credentials".into(),
                ));
            }
        };

        let config = hub_net::mail::SmtpConfig {
            host,
            port,
            username,
            password,
            tls,
        };

        let to: Vec<String> = args
            .get("to")
            .and_then(|v| match v {
                serde_json::Value::Array(arr) => Some(
                    arr.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect(),
                ),
                serde_json::Value::String(s) => Some(vec![s.clone()]),
                _ => None,
            })
            .unwrap_or_default();

        let cc: Vec<String> = args
            .get("cc")
            .and_then(|v| match v {
                serde_json::Value::Array(arr) => Some(
                    arr.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect(),
                ),
                serde_json::Value::String(s) => Some(vec![s.clone()]),
                _ => None,
            })
            .unwrap_or_default();

        let bcc: Vec<String> = args
            .get("bcc")
            .and_then(|v| match v {
                serde_json::Value::Array(arr) => Some(
                    arr.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect(),
                ),
                serde_json::Value::String(s) => Some(vec![s.clone()]),
                _ => None,
            })
            .unwrap_or_default();

        let subject = args.get("subject").and_then(|v| v.as_str()).unwrap_or("");

        let body_text = args.get("body").and_then(|v| v.as_str());
        let body_html = args.get("body_html").and_then(|v| v.as_str());

        let from = args
            .get("from")
            .and_then(|v| v.as_str())
            .unwrap_or(&from_address);

        if to.is_empty() {
            return Err(OperationError::InvalidArguments(
                "'to' field is required".into(),
            ));
        }

        let data = hub_net::mail::MailClient::send(
            &config, from, &to, &cc, &bcc, subject, body_text, body_html,
        )
        .await
        .map_err(OperationError::Network)?;

        Ok(ExecutionOutcome::Succeeded {
            executed: true,
            data,
        })
    }
}

fn substitute_path_params(template: &str, args: &mut serde_json::Value) -> String {
    let mut result = template.to_string();
    let mut to_remove = Vec::new();

    if let Some(obj) = args.as_object() {
        for (key, value) in obj {
            for placeholder in [format!("{{{key}}}"), format!("{{+{key}}}")] {
                if result.contains(&placeholder) {
                    let val_str = match value {
                        serde_json::Value::String(s) => s.clone(),
                        serde_json::Value::Number(n) => n.to_string(),
                        serde_json::Value::Bool(b) => b.to_string(),
                        _ => continue,
                    };
                    result = result.replace(&placeholder, &val_str);
                    if !to_remove.contains(key) {
                        to_remove.push(key.clone());
                    }
                }
            }
        }
    }

    if let Some(obj) = args.as_object_mut() {
        for key in &to_remove {
            obj.remove(key);
        }
    }

    result = result.replace("{userId}", "me");
    result = result.replace("{+userId}", "me");

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn substitutes_simple_param() {
        let mut args = serde_json::json!({"id": "123", "name": "test"});
        let result = substitute_path_params("/servers/{id}", &mut args);
        assert_eq!(result, "/servers/123");
        assert!(args.get("id").is_none());
        assert!(args.get("name").is_some());
    }

    #[test]
    fn substitutes_multiple_params() {
        let mut args = serde_json::json!({"userId": "me", "id": "abc123"});
        let result = substitute_path_params(
            "https://gmail.googleapis.com/gmail/v1/users/{userId}/messages/{id}",
            &mut args,
        );
        assert_eq!(
            result,
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/abc123"
        );
        assert!(args.as_object().unwrap().is_empty());
    }

    #[test]
    fn defaults_userid_to_me() {
        let mut args = serde_json::json!({"q": "is:unread"});
        let result = substitute_path_params(
            "https://gmail.googleapis.com/gmail/v1/users/{userId}/messages",
            &mut args,
        );
        assert_eq!(
            result,
            "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        );
        assert!(args.get("q").is_some());
    }

    #[test]
    fn handles_rfc6570_reserved() {
        let mut args = serde_json::json!({"name": "my-cert"});
        let result = substitute_path_params("/certificates/{+name}", &mut args);
        assert_eq!(result, "/certificates/my-cert");
        assert!(args.as_object().unwrap().is_empty());
    }

    #[test]
    fn leaves_non_matching_unchanged() {
        let mut args = serde_json::json!({"foo": "bar"});
        let result = substitute_path_params("/servers/{id}", &mut args);
        assert_eq!(result, "/servers/{id}");
        assert!(args.get("foo").is_some());
    }

    #[test]
    fn detects_absolute_url() {
        let path = "https://api.example.com/v1/resource";
        assert!(path.starts_with("https://"));

        let path = "/resource/{id}";
        assert!(!path.starts_with("http://") && !path.starts_with("https://"));
    }
}
