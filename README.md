# PLX Management System

This project is a proposed PWA for NetherGames that automates the manual parts of LiveOps work, with a focus on tournament tracking and reward handling. The goal is to reduce repetitive staff effort while still keeping sensitive actions under human approval.

## Problem Definition

- Tournament rewards are filtered, validated, and distributed manually, which is slow and inconsistent.
- Tournament data exists, but it is not packaged or checked efficiently for manager review.
- LiveOps work is highly manual overall, which reduces staff motivation for routine tasks.

## Enterprise Summary

NetherGames is one of the largest non-featured Minecraft Bedrock networks, with over six million registered players. Its LiveOps are supported by a large staff team, many of whom are volunteers handling moderation and player experience responsibilities.

The main challenge is that tournament operations still rely on manual checks, manual data packaging, and manual approvals. This creates delays, increases the chance of mistakes, and makes routine work less sustainable for staff.

## Proposed Idea

A PWA solution that uses preexisting API data to automate the repetitive parts of tournament operations while keeping manager and admin approval in the workflow.

### Core Features

- Three roles: Staff, Manager, Admin
- Encrypted storage of staff data
- Semi-structured intelligent system for assisting LiveOps workflows
- Tournament scheduling to support forecasting ahead of time
- Discord announcements for tournament updates and victor declarations through webhooks
- Data packaging of victor information such as XUID and IGN for manager approval
- Disqualification filtering to exclude ineligible players from the victor pool
- Tournament history storage for backup, late assignment, and reference

## Success Criteria

Tournament operations will be considered successful if the system:

- Reduces staff load by automating repetitive tournament tasks
- Keeps tournaments on schedule with fewer delays
- Speeds up reward processing by preparing victor data for approval more efficiently
- Preserves tournament history for analysis and late assignment support
- Improves operational consistency and reduces dependence on manual effort
