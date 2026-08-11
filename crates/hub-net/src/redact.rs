use std::borrow::Cow;

const SECRET_PATTERNS: [&str; 7] = [
    "authorization",
    "cookie",
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
];

pub fn redact_secrets<'a>(text: &'a str, explicit_secrets: &[&str]) -> Cow<'a, str> {
    let mut result = text.to_string();
    let mut changed = false;

    let lower = result.to_lowercase();
    for pattern in &SECRET_PATTERNS {
        if let Some(pos) = lower.find(pattern) {
            let after = pos + pattern.len();
            if let Some(sep) = result[after..].find([':', '=']) {
                let value_start = after + sep + 1;
                let trimmed = &result[value_start..].trim_start();
                let offset = value_start + (result[value_start..].len() - trimmed.len());
                let value_end = result[offset..]
                    .find('\n')
                    .map(|i| offset + i)
                    .unwrap_or(result.len());
                if value_end > offset {
                    result.replace_range(offset..value_end, "***");
                    changed = true;
                }
            }
        }
    }

    for secret in explicit_secrets {
        if !secret.is_empty() && result.contains(secret) {
            result = result.replace(secret, "***");
            changed = true;
        }
    }

    if changed {
        Cow::Owned(result)
    } else {
        Cow::Borrowed(text)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn redacts_authorization_header() {
        let input = "Authorization: Bearer sk-1234567890";
        let result = redact_secrets(input, &[]);
        assert!(result.contains("***"));
        assert!(!result.contains("sk-1234567890"));
    }

    #[test]
    fn redacts_explicit_secrets() {
        let input = "connecting to server with key abc123xyz";
        let result = redact_secrets(input, &["abc123xyz"]);
        assert!(result.contains("***"));
        assert!(!result.contains("abc123xyz"));
    }

    #[test]
    fn preserves_clean_text() {
        let input = "this is a normal log line";
        let result = redact_secrets(input, &[]);
        assert_eq!(&*result, input);
    }
}
