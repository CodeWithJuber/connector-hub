use crate::{RawOperation, SpecError};

pub struct OpenApiSpec {
    doc: serde_json::Value,
    provider: String,
}

impl OpenApiSpec {
    pub fn from_json(json: &str, provider: &str) -> Result<Self, SpecError> {
        let doc: serde_json::Value =
            serde_json::from_str(json).map_err(|e| SpecError::Parse(e.to_string()))?;
        Ok(Self {
            doc,
            provider: provider.into(),
        })
    }

    pub fn operations(&self) -> Result<Vec<RawOperation>, SpecError> {
        let paths = self
            .doc
            .get("paths")
            .and_then(|p| p.as_object())
            .ok_or_else(|| SpecError::MissingField("paths".into()))?;

        let mut ops = Vec::new();

        for (path, methods) in paths {
            let methods = methods
                .as_object()
                .ok_or_else(|| SpecError::Parse(format!("invalid path object: {path}")))?;

            for (method, details) in methods {
                if !["get", "post", "put", "patch", "delete", "head"].contains(&method.as_str()) {
                    continue;
                }

                let operation_id = details
                    .get("operationId")
                    .and_then(|v| v.as_str())
                    .unwrap_or(path.as_str());

                let summary = details
                    .get("summary")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");

                let description = details
                    .get("description")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");

                let tags: Vec<String> = details
                    .get("tags")
                    .and_then(|v| v.as_array())
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|v| v.as_str().map(String::from))
                            .collect()
                    })
                    .unwrap_or_default();

                let mutation_class = classify_http_method(method, operation_id);

                let parameters = details
                    .get("requestBody")
                    .and_then(|rb| rb.get("content"))
                    .and_then(|c| c.get("application/json"))
                    .and_then(|j| j.get("schema"))
                    .cloned()
                    .unwrap_or(serde_json::json!({"type": "object"}));

                ops.push(RawOperation {
                    id: format!("{}.{}", self.provider, operation_id),
                    provider: self.provider.clone(),
                    summary: summary.into(),
                    description: description.into(),
                    http_method: method.to_uppercase(),
                    path: path.clone(),
                    parameters,
                    mutation_class: mutation_class.into(),
                    tags,
                });
            }
        }

        Ok(ops)
    }
}

fn classify_http_method(method: &str, operation_id: &str) -> &'static str {
    let op_lower = operation_id.to_lowercase();

    if op_lower.contains("delete") || op_lower.contains("terminate") || op_lower.contains("destroy")
    {
        return "destructive";
    }

    match method {
        "get" | "head" => "read_only",
        "delete" => "destructive",
        "post" | "put" | "patch" => "mutating",
        _ => "read_only",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_minimal_openapi() {
        let spec = r#"{
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/servers": {
                    "get": {
                        "operationId": "list_servers",
                        "summary": "List all servers",
                        "tags": ["servers"]
                    },
                    "post": {
                        "operationId": "create_server",
                        "summary": "Create a server",
                        "tags": ["servers"]
                    }
                },
                "/servers/{id}": {
                    "delete": {
                        "operationId": "delete_server",
                        "summary": "Delete a server",
                        "tags": ["servers"]
                    }
                }
            }
        }"#;

        let parsed = OpenApiSpec::from_json(spec, "hetzner").unwrap();
        let ops = parsed.operations().unwrap();

        assert_eq!(ops.len(), 3);
        assert!(
            ops.iter()
                .any(|o| o.id == "hetzner.list_servers" && o.mutation_class == "read_only")
        );
        assert!(
            ops.iter()
                .any(|o| o.id == "hetzner.create_server" && o.mutation_class == "mutating")
        );
        assert!(
            ops.iter()
                .any(|o| o.id == "hetzner.delete_server" && o.mutation_class == "destructive")
        );
    }
}
