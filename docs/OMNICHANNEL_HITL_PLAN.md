# Omnichannel HITL Notification Architecture - Planning Document

## Status: WORK IN PROGRESS

This document outlines the planned architecture for omnichannel Human-in-the-Loop (HITL) notifications in Tactus. The current implementation consists of placeholder examples and architectural scaffolding.

## Problem Statement

When Tactus procedures pause waiting for human input (approval, review, input, escalation), users need to be notified across multiple channels:
- Slack/Discord/Teams for team notifications
- Mobile push notifications
- Email for escalations
- IDE notifications for local development

Currently, Tactus only supports CLI-based HITL interactions.

## Proposed Architecture

### Core Abstractions

1. **NotificationChannel Protocol** - Defines interface for notification plugins
2. **MultichannelHITLHandler** - Coordinates fanout to multiple channels
3. **HITLResponseHandler** - Processes responses with first-wins semantics
4. **Channel Loader** - Dynamic loading with optional dependencies

### Flow

```
Procedure calls Human.approve()
    ↓
MultichannelHITLHandler fans out to all enabled channels
    ↓
Procedure raises ProcedureWaitingForHuman (exit-and-resume)
    ↓
State persisted to StorageBackend
    ↓
User responds via any channel (Slack button, etc.)
    ↓
Response POSTed to deployment's webhook endpoint
    ↓
HITLResponseHandler processes response (first wins)
    ↓
Other channels cancelled/updated
    ↓
Procedure can be resumed with response
```

## Current State (WIP)

### Completed Scaffolding

- ✅ Protocol definitions (`tactus/protocols/notification.py`)
- ✅ MultichannelHITLHandler implementation
- ✅ HITLResponseHandler implementation
- ✅ Channel loader with optional dependencies
- ✅ Configuration schema and environment variables
- ✅ Optional dependencies in pyproject.toml

### Placeholder Channel Implementations

**These are example implementations that demonstrate the architecture but are NOT production-ready:**

- `tactus/adapters/channels/slack.py` - Slack with Block Kit (placeholder)
- `tactus/adapters/channels/discord.py` - Discord embeds (placeholder)
- `tactus/adapters/channels/teams.py` - Teams Adaptive Cards (placeholder)
- `tactus/adapters/channels/email.py` - Email notifications (placeholder)
- `tactus/adapters/channels/slack_interactivity.py` - Slack button handler (placeholder)

## Next Steps

### Phase 1: Real Channel Implementation

Need to identify which channel(s) to implement first based on actual requirements:

1. **Which notification channels are actually needed?**
   - Slack? Discord? Teams? Email? Mobile push?
   - What's the primary use case?

2. **For each channel, clarify:**
   - Authentication mechanism
   - Message format requirements
   - Interactive response capabilities
   - Rate limits and constraints

### Phase 2: Testing Strategy

- Unit tests for core handlers
- Mock channel implementations for testing
- Integration tests with real channels (behind feature flags)
- End-to-end testing with real deployments

### Phase 3: Production Readiness

- Error handling and retry logic
- Rate limiting and backpressure
- Monitoring and observability
- Documentation and examples
- Security review (token management, webhook signing)

## Open Questions

1. **Cloud backbone service**: Do we need a central service for mobile push and web dashboard notifications?
2. **Response coordination**: How do we handle concurrent responses from multiple channels?
3. **Channel priorities**: Should some channels be "primary" vs "fallback"?
4. **Timeout handling**: What happens if no response received within timeout?
5. **Deployment patterns**: How do different deployment scenarios (server, serverless, local) affect the design?

## Notes

- All channel implementations are currently placeholders/examples
- Core architecture is sound but needs real-world requirements to guide channel implementations
- Configuration system is in place and ready for production channels
- Exit-and-resume pattern integrates cleanly with existing Tactus runtime
