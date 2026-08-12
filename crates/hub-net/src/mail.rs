use lettre::message::{Mailbox, MessageBuilder, MultiPart, SinglePart, header::ContentType};
use lettre::transport::smtp::authentication::Credentials;
use lettre::{AsyncSmtpTransport, AsyncTransport, Message, Tokio1Executor};

use crate::NetError;

pub struct SmtpConfig {
    pub host: String,
    pub port: u16,
    pub username: String,
    pub password: String,
    pub tls: bool,
}

pub struct MailClient;

impl MailClient {
    #[allow(clippy::too_many_arguments)]
    pub async fn send(
        config: &SmtpConfig,
        from: &str,
        to: &[String],
        cc: &[String],
        bcc: &[String],
        subject: &str,
        body_text: Option<&str>,
        body_html: Option<&str>,
    ) -> Result<serde_json::Value, NetError> {
        let from_mailbox: Mailbox = from
            .parse()
            .map_err(|e| NetError::InvalidUrl(format!("invalid from address: {e}")))?;

        let mut builder: MessageBuilder = Message::builder().from(from_mailbox).subject(subject);

        for addr in to {
            let mailbox: Mailbox = addr
                .parse()
                .map_err(|e| NetError::InvalidUrl(format!("invalid to address '{addr}': {e}")))?;
            builder = builder.to(mailbox);
        }

        for addr in cc {
            let mailbox: Mailbox = addr
                .parse()
                .map_err(|e| NetError::InvalidUrl(format!("invalid cc address '{addr}': {e}")))?;
            builder = builder.cc(mailbox);
        }

        for addr in bcc {
            let mailbox: Mailbox = addr
                .parse()
                .map_err(|e| NetError::InvalidUrl(format!("invalid bcc address '{addr}': {e}")))?;
            builder = builder.bcc(mailbox);
        }

        let message = match (body_text, body_html) {
            (Some(text), Some(html)) => builder
                .multipart(MultiPart::alternative_plain_html(
                    text.to_string(),
                    html.to_string(),
                ))
                .map_err(|e| NetError::Connection(format!("failed to build email: {e}")))?,
            (Some(text), None) => builder
                .singlepart(
                    SinglePart::builder()
                        .header(ContentType::TEXT_PLAIN)
                        .body(text.to_string()),
                )
                .map_err(|e| NetError::Connection(format!("failed to build email: {e}")))?,
            (None, Some(html)) => builder
                .singlepart(
                    SinglePart::builder()
                        .header(ContentType::TEXT_HTML)
                        .body(html.to_string()),
                )
                .map_err(|e| NetError::Connection(format!("failed to build email: {e}")))?,
            (None, None) => builder
                .singlepart(
                    SinglePart::builder()
                        .header(ContentType::TEXT_PLAIN)
                        .body(String::new()),
                )
                .map_err(|e| NetError::Connection(format!("failed to build email: {e}")))?,
        };

        let creds = Credentials::new(config.username.clone(), config.password.clone());

        let transport = if config.tls {
            AsyncSmtpTransport::<Tokio1Executor>::relay(&config.host)
                .map_err(|e| NetError::Connection(format!("SMTP relay error: {e}")))?
                .port(config.port)
                .credentials(creds)
                .build()
        } else {
            AsyncSmtpTransport::<Tokio1Executor>::starttls_relay(&config.host)
                .map_err(|e| NetError::Connection(format!("SMTP STARTTLS error: {e}")))?
                .port(config.port)
                .credentials(creds)
                .build()
        };

        let response = transport
            .send(message)
            .await
            .map_err(|e| NetError::Connection(format!("SMTP send failed: {e}")))?;

        Ok(serde_json::json!({
            "ok": true,
            "smtp_code": response.code().to_string(),
            "message": response.message().collect::<Vec<_>>().join(" "),
        }))
    }
}
