use serde::{Deserialize, Serialize};

pub use hub_policy::MutationClass;

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct OperationId(pub String);

impl OperationId {
    pub fn new(provider: &str, method: &str) -> Self {
        Self(format!("{provider}.{method}"))
    }

    pub fn provider(&self) -> &str {
        self.0.split('.').next().unwrap_or(&self.0)
    }

    pub fn method(&self) -> &str {
        self.0.split_once('.').map_or("", |(_, m)| m)
    }
}

impl std::fmt::Display for OperationId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParameterSchema {
    pub json_schema: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Operation {
    pub id: OperationId,
    pub provider: String,
    pub summary: String,
    pub description: String,
    pub mutation_class: MutationClass,
    pub http_method: String,
    pub path_template: String,
    pub parameters: ParameterSchema,
    pub tags: Vec<String>,
}
