use std::net::IpAddr;

use crate::NetError;

const METADATA_IPS: [IpAddr; 2] = [
    IpAddr::V4(std::net::Ipv4Addr::new(169, 254, 169, 254)),
    IpAddr::V4(std::net::Ipv4Addr::new(169, 254, 170, 2)),
];

const METADATA_HOSTS: [&str; 2] = ["metadata.google.internal", "metadata.azure.internal"];

#[derive(Debug, Clone)]
pub struct ValidatedTarget {
    pub url: String,
    pub scheme: String,
    pub hostname: String,
    pub port: u16,
    pub addresses: Vec<IpAddr>,
    pub path: String,
}

#[derive(Debug, Clone)]
pub struct SsrfPolicy {
    pub allowed_schemes: Vec<String>,
    pub allowed_ports: Vec<u16>,
    pub max_redirects: usize,
    pub max_response_bytes: usize,
}

impl Default for SsrfPolicy {
    fn default() -> Self {
        Self {
            allowed_schemes: vec!["http".into(), "https".into()],
            allowed_ports: vec![80, 443],
            max_redirects: 5,
            max_response_bytes: 1_000_000,
        }
    }
}

impl SsrfPolicy {
    pub fn validate_address(addr: IpAddr) -> Result<(), NetError> {
        if METADATA_IPS.contains(&addr) {
            return Err(NetError::MetadataBlocked);
        }

        if addr.is_loopback() || addr.is_multicast() || addr.is_unspecified() {
            return Err(NetError::NonPublicAddress(addr));
        }

        match addr {
            IpAddr::V4(v4) => {
                if v4.is_private() || v4.is_link_local() {
                    return Err(NetError::NonPublicAddress(addr));
                }
                // 100.64.0.0/10 (CGNAT)
                if v4.octets()[0] == 100 && (v4.octets()[1] & 0xC0) == 64 {
                    return Err(NetError::NonPublicAddress(addr));
                }
            }
            IpAddr::V6(v6) => {
                if v6.is_loopback()
                    || (v6.segments()[0] & 0xffc0) == 0xfe80 // link-local
                    || (v6.segments()[0] & 0xfe00) == 0xfc00
                // ULA
                {
                    return Err(NetError::NonPublicAddress(addr));
                }
            }
        }

        Ok(())
    }

    pub fn validate_host(&self, host: &str) -> Result<(), NetError> {
        if host.is_empty() || host.len() > 253 {
            return Err(NetError::SsrfBlocked(
                "host must be 1-253 characters".into(),
            ));
        }

        let normalized = host.trim_end_matches('.').to_lowercase();
        if METADATA_HOSTS.contains(&normalized.as_str())
            || normalized.ends_with(".metadata.google.internal")
        {
            return Err(NetError::MetadataBlocked);
        }

        Ok(())
    }

    pub fn validate_url(&self, url: &str) -> Result<ValidatedTarget, NetError> {
        if url.len() > 4096 {
            return Err(NetError::InvalidUrl("URL exceeds 4096 characters".into()));
        }

        let parsed = url::Url::parse(url).map_err(|e| NetError::InvalidUrl(format!("{e}")))?;

        let scheme = parsed.scheme().to_lowercase();
        if !self.allowed_schemes.contains(&scheme) {
            return Err(NetError::SsrfBlocked(format!(
                "scheme '{scheme}' not allowed"
            )));
        }

        let hostname = parsed
            .host_str()
            .ok_or_else(|| NetError::InvalidUrl("no host in URL".into()))?;

        if parsed.username() != "" || parsed.password().is_some() {
            return Err(NetError::SsrfBlocked(
                "URL must not contain credentials".into(),
            ));
        }

        let port = parsed
            .port()
            .unwrap_or(if scheme == "https" { 443 } else { 80 });
        if !self.allowed_ports.contains(&port) {
            return Err(NetError::SsrfBlocked(format!("port {port} not allowed")));
        }

        self.validate_host(hostname)?;

        Ok(ValidatedTarget {
            url: url.to_string(),
            scheme,
            hostname: hostname.to_string(),
            port,
            addresses: Vec::new(),
            path: parsed.path().to_string(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::Ipv4Addr;

    #[test]
    fn blocks_loopback() {
        let result = SsrfPolicy::validate_address(IpAddr::V4(Ipv4Addr::LOCALHOST));
        assert!(result.is_err());
    }

    #[test]
    fn blocks_private() {
        let result = SsrfPolicy::validate_address(IpAddr::V4(Ipv4Addr::new(10, 0, 0, 1)));
        assert!(result.is_err());
    }

    #[test]
    fn blocks_link_local() {
        let result = SsrfPolicy::validate_address(IpAddr::V4(Ipv4Addr::new(169, 254, 1, 1)));
        assert!(result.is_err());
    }

    #[test]
    fn blocks_metadata_ip() {
        let result = SsrfPolicy::validate_address(IpAddr::V4(Ipv4Addr::new(169, 254, 169, 254)));
        assert!(result.is_err());
    }

    #[test]
    fn allows_public() {
        let result = SsrfPolicy::validate_address(IpAddr::V4(Ipv4Addr::new(8, 8, 8, 8)));
        assert!(result.is_ok());
    }

    #[test]
    fn blocks_metadata_host() {
        let policy = SsrfPolicy::default();
        assert!(policy.validate_host("metadata.google.internal").is_err());
        assert!(
            policy
                .validate_host("foo.metadata.google.internal")
                .is_err()
        );
    }

    #[test]
    fn blocks_credentials_in_url() {
        let policy = SsrfPolicy::default();
        assert!(
            policy
                .validate_url("https://user:pass@example.com/foo")
                .is_err()
        );
    }

    #[test]
    fn blocks_disallowed_port() {
        let policy = SsrfPolicy::default();
        assert!(policy.validate_url("https://example.com:8080/foo").is_err());
    }

    #[test]
    fn allows_valid_url() {
        let policy = SsrfPolicy::default();
        let result = policy.validate_url("https://api.hetzner.cloud/v1/servers");
        assert!(result.is_ok());
        let target = result.unwrap();
        assert_eq!(target.scheme, "https");
        assert_eq!(target.hostname, "api.hetzner.cloud");
        assert_eq!(target.port, 443);
    }
}
