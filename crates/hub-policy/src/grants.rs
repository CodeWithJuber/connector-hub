use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Effect {
    Allow,
    Ask,
    Deny,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Grant {
    pub provider: String,
    #[serde(default = "default_wildcard")]
    pub account: String,
    #[serde(default = "default_operations")]
    pub operations: Vec<String>,
    #[serde(default = "default_classes")]
    pub classes: Vec<String>,
    pub effect: Effect,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expires: Option<String>,
}

fn default_wildcard() -> String {
    "*".into()
}

fn default_operations() -> Vec<String> {
    vec!["*".into()]
}

fn default_classes() -> Vec<String> {
    vec!["read_only".into()]
}

impl Grant {
    pub fn matches(
        &self,
        provider: &str,
        account: Option<&str>,
        operation: &str,
        class: &str,
    ) -> bool {
        if self.provider != "*" && self.provider != provider {
            return false;
        }

        if self.account != "*"
            && let Some(acct) = account
            && self.account != acct
        {
            return false;
        }

        let op_matches = self.operations.iter().any(|pattern| {
            if pattern == "*" {
                return true;
            }
            if pattern.ends_with(".*") {
                let prefix = &pattern[..pattern.len() - 1];
                return operation.starts_with(prefix);
            }
            pattern == operation
        });

        if !op_matches {
            return false;
        }

        self.classes.iter().any(|c| c == "*" || c == class)
    }
}

#[derive(Debug, Clone)]
pub struct GrantDecision {
    pub effect: Effect,
    pub standing_approval: bool,
}
