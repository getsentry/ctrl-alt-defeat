# CLAUDE.md - Client-specific rules

## Critical Testing Rule
**ALWAYS read the FULL test output from the beginning**
- Don't grep for specific errors
- Don't tail the output
- Fix errors in ORDER - the first error often causes all subsequent failures
- Read line by line from the start to understand the actual problem

## API Response Handling
- Do NOT use `.get()` with fallback values on server responses
- Server responses should be consistent - if a field is missing, that's a bug
- Fail fast and loud when responses don't match expectations
