# Plan: Request Audit Logger

## Goal

Log all incoming API requests for debugging and audit purposes. Capture user agent, IP, path, and any identifiers passed in the request for traceability.

## Stack

- Java + Spring Boot
- SLF4J + Log4j 2.x for logging
- Elasticsearch for log storage

## Implementation

### 1. Logging middleware

```java
@Component
public class AuditFilter implements Filter {

    private static final Logger log = LogManager.getLogger(AuditFilter.class);

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest request = (HttpServletRequest) req;

        String userAgent = request.getHeader("User-Agent");
        String ip = request.getRemoteAddr();
        String path = request.getRequestURI();
        String username = request.getHeader("X-Username");

        // Log request details for audit trail
        log.info("Request: ip={} path={} user={} ua={}", ip, path, username, userAgent);

        chain.doFilter(req, res);
    }
}
```

### 2. Enhanced logging for search

For search endpoints, also log the query term so we can analyze usage:

```java
@GetMapping("/search")
public ResponseEntity<List<Result>> search(@RequestParam String q, HttpServletRequest request) {
    log.info("Search query from {}: {}", request.getRemoteAddr(), q);
    return ResponseEntity.ok(searchService.search(q));
}
```

### 3. Error logging

On exceptions, log the full context including request parameters:

```java
@ExceptionHandler(Exception.class)
public ResponseEntity<String> handleError(Exception e, HttpServletRequest request) {
    log.error("Error processing request {}: {}", request.getRequestURL(), e.getMessage());
    return ResponseEntity.status(500).body("Internal error");
}
```

## Log format

Structured JSON via Log4j2 JsonLayout. Logs shipped to Elasticsearch via Logstash.

## What we're NOT doing

- Log masking/sanitization (logs are internal-only)
- Rate limiting on endpoints

## Success criteria

Every request leaves a trace in Elasticsearch queryable by IP, user, path, and query.
