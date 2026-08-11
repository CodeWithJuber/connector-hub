use crate::PolicyError;
use crate::grants::{Effect, Grant, GrantDecision};

pub struct Policy {
    grants: Vec<Grant>,
}

impl Policy {
    pub fn new(grants: Vec<Grant>) -> Self {
        Self { grants }
    }

    pub fn deny_all() -> Self {
        Self { grants: Vec::new() }
    }

    pub fn from_toml(content: &str) -> Result<Self, PolicyError> {
        #[derive(serde::Deserialize)]
        struct PolicyFile {
            #[serde(default)]
            grant: Vec<Grant>,
        }

        let parsed: PolicyFile =
            toml::from_str(content).map_err(|e| PolicyError::FileError(e.to_string()))?;

        Ok(Self::new(parsed.grant))
    }

    pub fn check(
        &self,
        provider: &str,
        account: Option<&str>,
        operation: &str,
        mutation_class: crate::MutationClass,
    ) -> Result<GrantDecision, PolicyError> {
        let class_str = match mutation_class {
            crate::MutationClass::ReadOnly => "read_only",
            crate::MutationClass::Mutating => "mutating",
            crate::MutationClass::Destructive => "destructive",
        };

        let mut best_match: Option<&Grant> = None;

        for grant in &self.grants {
            if grant.matches(provider, account, operation, class_str) {
                match (&best_match, &grant.effect) {
                    (None, _) => best_match = Some(grant),
                    (Some(prev), _) if grant.provider != "*" && prev.provider == "*" => {
                        best_match = Some(grant);
                    }
                    _ => {}
                }
            }
        }

        match best_match {
            Some(grant) if grant.effect == Effect::Allow => Ok(GrantDecision {
                effect: Effect::Allow,
                standing_approval: grant.classes.iter().any(|c| c == "destructive" || c == "*"),
            }),
            Some(grant) if grant.effect == Effect::Ask => Ok(GrantDecision {
                effect: Effect::Ask,
                standing_approval: false,
            }),
            _ => {
                if mutation_class == crate::MutationClass::ReadOnly {
                    Ok(GrantDecision {
                        effect: Effect::Allow,
                        standing_approval: false,
                    })
                } else {
                    Err(PolicyError::Denied {
                        provider: provider.into(),
                        operation: operation.into(),
                        reason: "no matching grant; default is deny".into(),
                    })
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_allows_read_only() {
        let policy = Policy::deny_all();
        let result = policy.check(
            "hetzner",
            None,
            "hetzner.list_servers",
            crate::MutationClass::ReadOnly,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn default_denies_mutating() {
        let policy = Policy::deny_all();
        let result = policy.check(
            "hetzner",
            None,
            "hetzner.create_server",
            crate::MutationClass::Mutating,
        );
        assert!(result.is_err());
    }

    #[test]
    fn grant_allows_mutating() {
        let policy = Policy::from_toml(
            r#"
[[grant]]
provider = "hetzner"
operations = ["hetzner.*"]
classes = ["read_only", "mutating"]
effect = "allow"
"#,
        )
        .unwrap();

        let result = policy.check(
            "hetzner",
            None,
            "hetzner.create_server",
            crate::MutationClass::Mutating,
        );
        assert!(result.is_ok());
    }

    #[test]
    fn destructive_denied_without_explicit_grant() {
        let policy = Policy::from_toml(
            r#"
[[grant]]
provider = "hetzner"
operations = ["hetzner.*"]
classes = ["read_only", "mutating"]
effect = "allow"
"#,
        )
        .unwrap();

        let result = policy.check(
            "hetzner",
            None,
            "hetzner.delete_server",
            crate::MutationClass::Destructive,
        );
        assert!(result.is_err());
    }
}
