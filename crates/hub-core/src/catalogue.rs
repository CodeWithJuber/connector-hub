use std::collections::HashMap;

use crate::operation::{MutationClass, Operation, OperationId};

pub struct Catalogue {
    operations: HashMap<OperationId, Operation>,
    by_provider: HashMap<String, Vec<OperationId>>,
}

impl Catalogue {
    pub fn new() -> Self {
        Self {
            operations: HashMap::new(),
            by_provider: HashMap::new(),
        }
    }

    pub fn register(&mut self, op: Operation) {
        let provider = op.provider.clone();
        let id = op.id.clone();
        self.operations.insert(id.clone(), op);
        self.by_provider.entry(provider).or_default().push(id);
    }

    pub fn get(&self, id: &OperationId) -> Option<&Operation> {
        self.operations.get(id)
    }

    pub fn search(&self, query: &str, provider: Option<&str>) -> Vec<&Operation> {
        let query_lower = query.to_lowercase();
        let terms: Vec<&str> = query_lower.split_whitespace().collect();

        self.operations
            .values()
            .filter(|op| {
                if let Some(p) = provider
                    && op.provider != p
                {
                    return false;
                }
                let haystack = format!(
                    "{} {} {} {}",
                    op.id,
                    op.summary,
                    op.description,
                    op.tags.join(" ")
                )
                .to_lowercase();
                terms.iter().all(|t| haystack.contains(t))
            })
            .collect()
    }

    pub fn providers(&self) -> Vec<&str> {
        let mut providers: Vec<&str> = self.by_provider.keys().map(|s| s.as_str()).collect();
        providers.sort();
        providers
    }

    pub fn operations_for_provider(&self, provider: &str) -> Vec<&Operation> {
        self.by_provider
            .get(provider)
            .map(|ids| {
                ids.iter()
                    .filter_map(|id| self.operations.get(id))
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn all_operations(&self) -> impl Iterator<Item = &Operation> {
        self.operations.values()
    }

    pub fn len(&self) -> usize {
        self.operations.len()
    }

    pub fn is_empty(&self) -> bool {
        self.operations.is_empty()
    }

    pub fn destructive_operations(&self) -> Vec<&Operation> {
        self.operations
            .values()
            .filter(|op| op.mutation_class == MutationClass::Destructive)
            .collect()
    }
}

impl Default for Catalogue {
    fn default() -> Self {
        Self::new()
    }
}
