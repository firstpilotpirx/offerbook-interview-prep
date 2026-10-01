---
stage: tech
sources: [kafka-docs]
last_verified: 2026-09-30
---

@@ tech.services.messaging
Consumers read a topic by partitions. When consumers cannot [[keep up with]] the producer, the lag grows.

@@ tech.services.consistency
Between services we accept eventual consistency. [[The trade-off is]] stale data on reads.

@@ tech.frameworks.transactional

### In short

`@Transactional` works through a **proxy**. Spring wraps the bean; an external call goes through `TransactionInterceptor`, which opens a transaction, calls the method and then commits or rolls back. The transaction is bound to the thread, so it does not propagate to `@Async` methods or other threads. The classic trap is self-invocation: calling the method from the same class bypasses the proxy.

### Interview Q&A

- **How does @Transactional work?** It is proxy-based. The interceptor asks the transaction manager to begin a transaction, calls the method, then commits or rolls back.
- **Why doesn't it work for internal calls?** `this.method()` bypasses the proxy, so no transaction is started. Move the method to another bean or use TransactionTemplate.
- **Does it roll back on a checked exception?** Not by default — only on RuntimeException and Error. Use `rollbackFor`.
- **REQUIRED vs REQUIRES_NEW?** REQUIRED joins the current transaction; REQUIRES_NEW suspends it and opens a new one, for example for an audit record that must survive a rollback.
