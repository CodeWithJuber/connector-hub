use serde::{Deserialize, Serialize};
use std::fs::{File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub timestamp: String,
    pub provider: String,
    pub operation: String,
    pub account: Option<String>,
    pub effect: String,
    pub reason: String,
    pub prev_hash: String,
    pub hash: String,
}

pub struct AuditLedger {
    path: std::path::PathBuf,
    prev_hash: String,
}

impl AuditLedger {
    pub fn open(path: &Path) -> Result<Self, std::io::Error> {
        let prev_hash = if path.exists() {
            let file = File::open(path)?;
            let reader = BufReader::new(file);
            let mut last_hash = String::from("genesis");
            for line in reader.lines() {
                let line = line?;
                if line.trim().is_empty() {
                    continue;
                }
                if let Ok(entry) = serde_json::from_str::<AuditEntry>(&line) {
                    last_hash = entry.hash;
                }
            }
            last_hash
        } else {
            "genesis".into()
        };

        Ok(Self {
            path: path.to_path_buf(),
            prev_hash,
        })
    }

    pub fn append(
        &mut self,
        provider: &str,
        operation: &str,
        account: Option<&str>,
        effect: &str,
        reason: &str,
    ) -> Result<AuditEntry, std::io::Error> {
        let timestamp = format!(
            "{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs()
        );

        let content = format!(
            "{}:{}:{}:{}:{}:{}:{}",
            timestamp,
            provider,
            operation,
            account.unwrap_or("*"),
            effect,
            reason,
            self.prev_hash,
        );
        let hash = blake3::hash(content.as_bytes()).to_hex().to_string();

        let entry = AuditEntry {
            timestamp,
            provider: provider.into(),
            operation: operation.into(),
            account: account.map(String::from),
            effect: effect.into(),
            reason: reason.into(),
            prev_hash: self.prev_hash.clone(),
            hash: hash.clone(),
        };

        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;

        writeln!(file, "{}", serde_json::to_string(&entry).unwrap())?;
        self.prev_hash = hash;

        Ok(entry)
    }

    pub fn verify(path: &Path) -> Result<usize, String> {
        let file = File::open(path).map_err(|e| format!("cannot open ledger: {e}"))?;
        let reader = BufReader::new(file);
        let mut prev_hash = String::from("genesis");
        let mut count = 0;

        for (i, line) in reader.lines().enumerate() {
            let line = line.map_err(|e| format!("read error at line {i}: {e}"))?;
            if line.trim().is_empty() {
                continue;
            }

            let entry: AuditEntry =
                serde_json::from_str(&line).map_err(|e| format!("parse error at line {i}: {e}"))?;

            if entry.prev_hash != prev_hash {
                return Err(format!(
                    "chain broken at line {i}: expected prev_hash={prev_hash}, got {}",
                    entry.prev_hash
                ));
            }

            let content = format!(
                "{}:{}:{}:{}:{}:{}:{}",
                entry.timestamp,
                entry.provider,
                entry.operation,
                entry.account.as_deref().unwrap_or("*"),
                entry.effect,
                entry.reason,
                entry.prev_hash,
            );
            let expected = blake3::hash(content.as_bytes()).to_hex().to_string();

            if entry.hash != expected {
                return Err(format!(
                    "hash mismatch at line {i}: expected {expected}, got {}",
                    entry.hash
                ));
            }

            prev_hash = entry.hash;
            count += 1;
        }

        Ok(count)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn append_and_verify() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("audit.jsonl");

        let mut ledger = AuditLedger::open(&path).unwrap();
        ledger
            .append(
                "hetzner",
                "delete_server",
                Some("default"),
                "denied",
                "no confirmation token",
            )
            .unwrap();
        ledger
            .append(
                "gmail",
                "send",
                Some("support@example.com"),
                "allowed",
                "policy grant",
            )
            .unwrap();
        ledger
            .append(
                "hetzner",
                "delete_server",
                Some("default"),
                "allowed",
                "confirmed",
            )
            .unwrap();

        let count = AuditLedger::verify(&path).unwrap();
        assert_eq!(count, 3);
    }

    #[test]
    fn detects_tampering() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("audit.jsonl");

        let mut ledger = AuditLedger::open(&path).unwrap();
        ledger.append("test", "op1", None, "allowed", "ok").unwrap();
        ledger.append("test", "op2", None, "allowed", "ok").unwrap();

        let content = fs::read_to_string(&path).unwrap();
        let tampered = content.replacen("op1", "op9", 1);
        fs::write(&path, tampered).unwrap();

        assert!(AuditLedger::verify(&path).is_err());
    }
}
