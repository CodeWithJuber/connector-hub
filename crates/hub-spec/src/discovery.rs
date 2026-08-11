use crate::{RawOperation, SpecError};

pub struct GoogleDiscoverySpec {
    doc: serde_json::Value,
    provider: String,
}

impl GoogleDiscoverySpec {
    pub fn from_json(json: &str, provider: &str) -> Result<Self, SpecError> {
        let doc: serde_json::Value =
            serde_json::from_str(json).map_err(|e| SpecError::Parse(e.to_string()))?;
        Ok(Self {
            doc,
            provider: provider.into(),
        })
    }

    pub fn operations(&self) -> Result<Vec<RawOperation>, SpecError> {
        let base_url = self
            .doc
            .get("baseUrl")
            .and_then(|v| v.as_str())
            .unwrap_or("");

        let mut ops = Vec::new();
        if let Some(resources) = self.doc.get("resources").and_then(|r| r.as_object()) {
            self.extract_resources(resources, "", base_url, &mut ops);
        }
        Ok(ops)
    }

    fn extract_resources(
        &self,
        resources: &serde_json::Map<String, serde_json::Value>,
        prefix: &str,
        base_url: &str,
        ops: &mut Vec<RawOperation>,
    ) {
        for (name, resource) in resources {
            let resource_path = if prefix.is_empty() {
                name.clone()
            } else {
                format!("{prefix}.{name}")
            };

            if let Some(methods) = resource.get("methods").and_then(|m| m.as_object()) {
                for (method_name, method) in methods {
                    let id = method
                        .get("id")
                        .and_then(|v| v.as_str())
                        .unwrap_or(method_name);

                    let http_method = method
                        .get("httpMethod")
                        .and_then(|v| v.as_str())
                        .unwrap_or("GET");

                    let path = method.get("path").and_then(|v| v.as_str()).unwrap_or("");

                    let description = method
                        .get("description")
                        .and_then(|v| v.as_str())
                        .unwrap_or("");

                    let mutation_class = classify_discovery_method(http_method, method_name);

                    let parameters = method
                        .get("parameters")
                        .cloned()
                        .unwrap_or(serde_json::json!({}));

                    ops.push(RawOperation {
                        id: format!("{}.{}", self.provider, id),
                        provider: self.provider.clone(),
                        summary: format!("{resource_path}.{method_name}"),
                        description: description.into(),
                        http_method: http_method.into(),
                        path: format!("{base_url}{path}"),
                        parameters,
                        mutation_class: mutation_class.into(),
                        tags: vec![resource_path.clone()],
                    });
                }
            }

            if let Some(sub) = resource.get("resources").and_then(|r| r.as_object()) {
                self.extract_resources(sub, &resource_path, base_url, ops);
            }
        }
    }
}

fn classify_discovery_method(http_method: &str, method_name: &str) -> &'static str {
    let name_lower = method_name.to_lowercase();
    if name_lower.contains("delete") || name_lower.contains("trash") {
        return "destructive";
    }
    match http_method {
        "GET" => "read_only",
        "DELETE" => "destructive",
        "POST" | "PUT" | "PATCH" => "mutating",
        _ => "read_only",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_discovery_format() {
        let spec = r#"{
            "baseUrl": "https://gmail.googleapis.com/gmail/v1/users/",
            "resources": {
                "users": {
                    "resources": {
                        "messages": {
                            "methods": {
                                "list": {
                                    "id": "gmail.users.messages.list",
                                    "httpMethod": "GET",
                                    "path": "{userId}/messages",
                                    "description": "Lists the messages in the user's mailbox."
                                },
                                "get": {
                                    "id": "gmail.users.messages.get",
                                    "httpMethod": "GET",
                                    "path": "{userId}/messages/{id}",
                                    "description": "Gets the specified message."
                                },
                                "send": {
                                    "id": "gmail.users.messages.send",
                                    "httpMethod": "POST",
                                    "path": "{userId}/messages/send",
                                    "description": "Sends the specified message."
                                },
                                "delete": {
                                    "id": "gmail.users.messages.delete",
                                    "httpMethod": "DELETE",
                                    "path": "{userId}/messages/{id}",
                                    "description": "Immediately and permanently deletes the specified message."
                                }
                            }
                        }
                    }
                }
            }
        }"#;

        let parsed = GoogleDiscoverySpec::from_json(spec, "gmail").unwrap();
        let ops = parsed.operations().unwrap();

        assert_eq!(ops.len(), 4);
        assert!(
            ops.iter()
                .any(|o| o.id == "gmail.gmail.users.messages.list"
                    && o.mutation_class == "read_only")
        );
        assert!(
            ops.iter().any(
                |o| o.id == "gmail.gmail.users.messages.send" && o.mutation_class == "mutating"
            )
        );
        assert!(
            ops.iter()
                .any(|o| o.id == "gmail.gmail.users.messages.delete"
                    && o.mutation_class == "destructive")
        );
    }
}
