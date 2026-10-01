# Topic material format

A material is **a lesson from which you can learn the topic from scratch and review it before the interview**, not a table-of-contents summary. The person reads it on the prep page; answers to questions there are collapsed so they can answer on their own first.

Checked by a script: `run depth.py --dir <folder>` (and `validate_content.py --require-depth` before publishing). If it fails — keep writing, do not publish.

## Length by priority

Minimum word counts:

| Priority | Russian | English as explanation language | Other explanation language | EN companion | Interview questions |
|---|---|---|---|---|---|
| 1 must | from 400 (usually 500–900) | from 320 | from 350 | from 150 | from 4 |
| 2 important | from 250 | from 200 | from 220 | from 100 | from 3 |
| 3 optional | from 120 | from 100 | from 110 | from 60 | from 2 |

The lesson language is the explanation language chosen at the start of the wizard. The EN companion is a short English version for those training their English. For a language other than Russian and English, `depth.py` checks the number of sections (4 for priority 1–2, 2 for priority 3) and questions in the form `- **…?**`.

Cross-cutting sections are not lessons; they have their own formats:

| Section | Format | Minimum |
|---|---|---|
| `stories.*` — my systems and stories | `### Situation`, `### Task`, `### Action`, `### Result` (Russian lessons: `### Ситуация`, `### Задача`, `### Действия`, `### Результат`); under "Action" — what the person did **personally**, under "Result" — numbers | RU 180, EN 100 |
| `answers.*` — my answers | a spoken answer for 1–2 minutes, first person, no bureaucratese; in EN — in the same voice | RU 60, EN 40 |
| `questions.*` — questions for them | a list of questions, each noting what you want to learn from it | 40 |

Code in ```` ``` ```` blocks does not count toward length. A "one week" deadline is no reason to go below the minimum — cut the number of topics, not the depth.

## Sections (`###` headings, with exactly these words)

The headings are matched by `tools/depth.py`, so use these exact words in the lesson's language. English is listed first; the Russian variant (for Russian-language lessons) is given next to each.

1. `### In short` (RU: `### Суть`) — **required.** 2–4 paragraphs in your own words: what it is, what problem it solves, how it works inside. So that someone who doesn't know the topic understands. An analogy, if it helps.
2. `### How it works` (RU: `### Как устроено`) — **required for priorities 1–2.** The mechanism step by step, a flow or state diagram as a list, a code example with comments. For infrastructure — the configuration and what matters in it.
3. `### Interview Q&A` (RU: `### Вопросы на интервью`) — **required.** A list, each item: `- **Question?** Answer in 2–5 sentences`, the way to say it out loud. Common ones first, then tricky ones.
4. `### Pitfalls` (RU: `### Ловушки`) — what gets confused, what interviewers catch people on, typical production mistakes.
5. `### When to choose what` (RU: `### Когда что выбирать`) — if there are alternatives: a comparison table.
6. `### From your experience` (RU: `### Из вашего опыта`) — a bridge to the person's CV: which of their projects fits here and one or two sentences on how to tell it. Only facts from the CV and answers.
7. `### Check yourself` (RU: `### Проверь себя`) — **required for priorities 1–2.** 3–5 questions in the same format `- **Question?** Short answer` — collapsed on the page.
8. `### Sources` (RU: `### Источники`) — **one line without links**: "From the book: Kleppmann, DDIA, ch. 7; Spring Reference — Transactions". Do not fetch anything for sources: people don't follow the links, and tokens get spent. Versions, limits, prices, defaults you are not sure of — mark "verify before the interview".

Required by `depth.py`: priority 1–2 — In short, How it works, Interview Q&A, Check yourself (RU: Суть, Как устроено, Вопросы на интервью, Проверь себя); priority 3 — In short, Interview Q&A (RU: Суть, Вопросы на интервью).

**EN companion** (a short English version next to a lesson in another language, for interviews in English): `### In short` (the gist, how to say it), `### Interview Q&A` (questions in the same format), optionally `### Key phrases`. It is not a translation of the lesson but what is said out loud.

## Rules

- Length benchmark — the working portal with 404 topics: median lesson ~330 words, 500+ for must-know topics; almost every one has an "In the interview" part — a ready-to-say formulation.
- Theory from the "Foundations" section is tied to the person's technology: principle → how it looks in their stack and projects.

- Write by explaining, not listing. A comma-separated list of terms is a table of contents — not allowed.
- Every term on first use — explained in parentheses or in a separate sentence.
- Examples — from the person's stack (language, framework, database from the questionnaire) and their projects.
- If the topic comes from the vacancy — one sentence on how they probably use it, and a question worth asking them.
- Mark key English terms in `.en.md` as `[[term]]` — they are linked to the vocabulary.

## Theory and technology — what goes where

Rule: **the general goes in "Foundations", the specific goes in the technology section.** Overlap via a link, not a retelling.

| In the stack | "Foundations" (theory.*) — how a class of systems works | Technology section (tech.*) — how this one works |
|---|---|---|
| PostgreSQL | normalization, ACID and isolation anomalies, MVCC as an idea, B-tree as a structure | MVCC in Postgres: xmin/xmax, VACUUM, HOT, WAL, planner |
| Kafka | log vs queue, delivery semantics, outbox | partitions and offsets, consumer groups and rebalancing, acks and ISR, idempotent producer |
| Redis | caching strategies, invalidation, eviction | single-threadedness, data structures, RDB/AOF persistence, cluster |
| ClickHouse | columnar storage, LSM vs B-tree | MergeTree, partitions and sorting key, materialized views |
| microservices | sagas, outbox, CQRS, resilience | how the person did it: Spring, Resilience4j, Kafka |

Theory level — **understand and explain in an interview, including system design**: what it is, why, what trade-offs, how it shows up in their system. No proofs or academic detail.

**Books are the basis of the content; the text is your own.** Which topics to cover, in what order, which trade-offs and examples matter — comes from canonical books. But the lesson is written in your own words, with examples from the person's stack: no quotes and no close paraphrase of the book. That isn't needed anyway — the value is in an understood mechanism, not in the author's wording.

**The primary source beats retellings.** Convey the meaning of the original authors — Fowler, Evans, Robert Martin, the "Gang of Four", Kleppmann, Richardson, Newman, Nygard, Hohpe — not secondary articles and blogs based on them. Terms and definitions — as the author has them: Aggregate as in Evans, Unit of Work as in Fowler, SOLID principles as in Martin. If the industry understands a term differently from the author — say so in one sentence: it is a common interview question.

Books — from the profile registry (`sources`): Kleppmann "Designing Data-Intensive Applications", Richardson "Microservices Patterns", Newman "Building Microservices", Fowler PoEAA, Hohpe EIP, GoF, Evans DDD, Petrov "Database Internals", Nygard "Release It!", Google SRE. In the lesson's "Sources" — the book and chapter or section if you know it exactly; if not — just the book.

## Estimation lessons (design.estimation.*)

- Numbers — **in orders of magnitude** and rounded: "read from memory ~100 ns, from SSD ~100 µs, within a data center ~0.5 ms, between continents ~100 ms".
- Every topic has a worked back-of-the-envelope example: "10M DAU × 20 actions = 200M per day ≈ 2,300 RPS on average, ×5–10 at peak".
- Reliability — a table of nines in minutes of downtime per month and per year; components in series multiply availability, parallel ones multiply the complements (failure probabilities).
- Cost — only orders of magnitude and relative comparison (what grows more expensive: traffic, storage, compute); specific prices — "verify before the interview", they change.
- In "Interview Q&A" — how to state assumptions out loud.

## System design problems (design.cases.*)

Not a worked solution but a **plan for the conversation**: what to pin down, what to ask, what to keep in mind while designing. The person builds the design themselves in the interview; the lesson makes sure they scope it well and show they understand the problem. No full architecture, no step-by-step answer. Based on Alex Xu "System Design Interview" (volumes 1–2) and DDIA; the text is your own.

Sections (English, with the Russian variant for Russian-language lessons), all four required:

- `### Functional requirements` (RU: `### Функциональные требования`) — what the system must do: 4–7 bullets, core first, then "nice to have" marked as such. Which ones to propose as in scope and which to cut out loud.
- `### Non-functional requirements` (RU: `### Нефункциональные требования`) — scale (users, RPS, data volume — rough numbers to confirm), latency, availability, consistency, durability, security and cost. For each: the target you would propose and why it matters for this problem.
- `### What to ask the interviewer` (RU: `### Что уточнить у интервьюера`) — the clarifying questions, grouped: about functionality, about load and data, about constraints. For each — why you ask (what in the design depends on the answer). Plus how to run the conversation: say assumptions out loud and get a nod, check in before going deep, offer two options and ask which to explore, keep an eye on the time.
- `### What to watch for in the implementation` (RU: `### На что обратить внимание при реализации`) — the 5–8 things that make or break this system: the key trade-off, the bottleneck, the hard part (idempotency, ordering, hot keys, consistency between stores…), what fails and how it degrades, which back-of-the-envelope number decides the storage or the cache. Points to keep in mind, not a solution.

Required by `depth.py`: all four (RU: Функциональные требования, Нефункциональные требования, Что уточнить у интервьюера, На что обратить внимание при реализации).

Length: priority 1 — from 300 words, 2 — from 200, 3 — from 120. Problems close to the vacancy's domain (payments, exchange, wallet, notifications) — priority 1 and at the start; domain problems not in the catalog are added based on the vacancy with id `design.cases.<slug>`.

## Example — priority 1, English as the explanation language

A full lesson (in `.en.md` when the explanation language is English):

```markdown
@@ tech.frameworks.transactional

### In short

`@Transactional` is how you tell Spring: "this method must run in a single database transaction". Spring doesn't inject anything into the method's code. It wraps the bean in a **proxy** — an intermediary object with the same interface. When the method is called from outside, the proxy runs first: it opens a transaction, calls the real method, and then commits or rolls back the transaction depending on the result.

Almost every interview question about `@Transactional` boils down to one thing: **a transaction exists only where the call went through the proxy**. Hence the main traps — calling a method from inside the same class, private methods, work on another thread.

The current transaction is stored in a `ThreadLocal` — it is bound to the thread. That is why it doesn't carry over into an `@Async` method, a `CompletableFuture` on a different executor, or a Kafka consumer thread.

### How it works

1. On context startup Spring finds beans with `@Transactional` and creates proxies for them: a JDK dynamic proxy if the bean implements an interface and it is configured that way, otherwise a CGLIB subclass (CGLIB is the default in Spring Boot).
2. An external call lands in `TransactionInterceptor`.
3. The interceptor reads the annotation attributes (propagation, isolation, readOnly, timeout, rollbackFor) and asks the `PlatformTransactionManager` (for JPA — `JpaTransactionManager`) whether there is already a transaction on this thread.
4. The propagation decision: `REQUIRED` (default) — join the existing one or open a new one; `REQUIRES_NEW` — suspend the current one and open a separate one; `SUPPORTS`, `MANDATORY`, `NEVER`, `NESTED` — less common.
5. The method runs. Returns normally — commit. Throws — rollback, **but only for unchecked exceptions** (`RuntimeException`, `Error`). A checked one (`IOException`) commits the transaction by default — configurable via `rollbackFor`.

    @Service
    public class TransferService {
        @Transactional
        public void transfer(long from, long to, BigDecimal amount) {
            accounts.debit(from, amount);   // both operations —
            accounts.credit(to, amount);    // in one transaction
        }

        public void transferAll(List<Transfer> list) {
            list.forEach(t -> transfer(t.from(), t.to(), t.amount())); // ⚠ self-invocation: the proxy is bypassed,
        }                                                               //   transfer() has no transaction here
    }

### Interview Q&A

- **How does @Transactional work?** Through a proxy. Spring wraps the bean, and on an external call TransactionInterceptor opens a transaction via the TransactionManager, calls the method, and commits or rolls back. The transaction is bound to the thread via ThreadLocal.
- **Why doesn't calling the method from inside the class work?** A `this.method()` call goes straight to the object, bypassing the proxy, so the annotation has no effect. Fixes: move the method to a separate bean, inject the bean into itself through the proxy, or use TransactionTemplate.
- **Will the transaction roll back on a checked exception?** Not by default — rollback happens only on RuntimeException and Error. You need `rollbackFor = Exception.class` or your own unchecked exception.
- **How does REQUIRED differ from REQUIRES_NEW?** REQUIRED joins the existing transaction — if something fails inside, everything rolls back. REQUIRES_NEW suspends the outer one and opens its own — for example, to write an audit record even if the main operation rolls back. The cost is a second database connection.
- **What does readOnly = true give you?** A hint: Hibernate skips dirty checking and flush, the driver may route the query to a replica. It is not a write ban at the database level — that depends on the driver and the database.

### Pitfalls

- The annotation on a private method silently does nothing (verify which modifiers your Spring version supports).
- An exception caught inside the method and not rethrown — the transaction commits.
- A long external call (HTTP, Kafka) inside a transaction holds a pool connection — under load the pool runs out.
- `@Transactional` on a method that sends a message to Kafka: the message goes out even if the transaction later rolls back. You need an outbox or a transactional producer.

### From your experience

In the indexer you wrote events in batches. A good story: why a batch is written in one transaction, what happens on a crash mid-batch, and how you ensured idempotent rewrites.

### Check yourself

- **Which Spring class actually opens the transaction?** TransactionInterceptor, via PlatformTransactionManager.
- **Will there be a transaction in an @Async method called from a transactional one?** Its own — only if the @Async method has @Transactional; the outer one does not carry over, it is on another thread.
- **How do you write an audit record even if the main operation rolls back?** A separate bean with REQUIRES_NEW.

### Sources

- Spring Framework Reference — Transaction Management (verify the propagation section for your version before the interview).
```

### EN companion of the same block

When English is **not** a chosen course language but English is trained (`english-train`), the `.en.md` file holds a short companion instead (priority 1). When English is chosen, `.en.md` is a full lesson like any other language:

```markdown
@@ tech.frameworks.transactional

### In short

`@Transactional` works through a **proxy**. Spring wraps the bean; an external call goes through `TransactionInterceptor`, which opens a transaction, calls the method and then commits or rolls back. The transaction is bound to the thread, so it does not propagate to `@Async` methods or other threads. The classic trap is self-invocation: calling the method from the same class bypasses the proxy.

### Interview Q&A

- **How does @Transactional work?** It is proxy-based. The interceptor asks the transaction manager to begin a transaction, calls the method, then commits or rolls back.
- **Why doesn't it work for internal calls?** `this.method()` bypasses the proxy, so no transaction is started. Move the method to another bean or use TransactionTemplate.
- **Does it roll back on a checked exception?** Not by default — only on RuntimeException and Error. Use `rollbackFor`.
- **REQUIRED vs REQUIRES_NEW?** REQUIRED joins the current transaction; REQUIRES_NEW suspends it and opens a new one, for example for an audit record that must survive a rollback.
```

### Example of a Russian-language lesson (same block)

The same priority-1 lesson when the explanation language is Russian (`.ru.md`), with the Russian section headings `depth.py` expects. Kept in Russian on purpose as reference data:

```markdown
@@ tech.frameworks.transactional

### Суть

`@Transactional` — способ сказать Spring: «этот метод должен выполниться в одной транзакции базы». Сам Spring в код метода ничего не вписывает. Он оборачивает бин в **прокси** — объект-посредник с тем же интерфейсом. Когда снаружи вызывают метод, сначала срабатывает прокси: открывает транзакцию, вызывает настоящий метод, а потом фиксирует (commit) или откатывает (rollback) транзакцию в зависимости от результата.

Почти все вопросы на собесе про `@Transactional` сводятся к одному: **транзакция существует только там, где вызов прошёл через прокси**. Отсюда и главные ловушки — вызов метода изнутри того же класса, приватные методы, работа в другом потоке.

Текущая транзакция хранится в `ThreadLocal` — привязана к потоку. Поэтому она не переходит в `@Async`-метод, в `CompletableFuture` с другим executor или в поток Kafka-консьюмера.

### Как устроено

1. При старте контекста Spring находит бины с `@Transactional` и создаёт для них прокси: JDK dynamic proxy, если бин реализует интерфейс и так настроено, иначе CGLIB-подкласс (в Spring Boot по умолчанию CGLIB).
2. Вызов снаружи попадает в `TransactionInterceptor`.
3. Интерсептор читает атрибуты аннотации (propagation, isolation, readOnly, timeout, rollbackFor) и спрашивает `PlatformTransactionManager` (для JPA — `JpaTransactionManager`): есть ли уже транзакция в этом потоке.
4. Решение по propagation: `REQUIRED` (по умолчанию) — присоединиться к существующей или открыть новую; `REQUIRES_NEW` — приостановить текущую и открыть отдельную; `SUPPORTS`, `MANDATORY`, `NEVER`, `NESTED` — реже.
5. Метод выполняется. Вышел нормально — commit. Вылетело исключение — rollback, **но только для непроверяемых** (`RuntimeException`, `Error`). Проверяемое (`IOException`) по умолчанию транзакцию фиксирует — это настраивается через `rollbackFor`.

    @Service
    public class TransferService {
        @Transactional
        public void transfer(long from, long to, BigDecimal amount) {
            accounts.debit(from, amount);   // обе операции —
            accounts.credit(to, amount);    // в одной транзакции
        }

        public void transferAll(List<Transfer> list) {
            list.forEach(t -> transfer(t.from(), t.to(), t.amount())); // ⚠ self-invocation: прокси не участвует,
        }                                                               //   транзакции у transfer() здесь нет
    }

### Вопросы на интервью

- **Как работает @Transactional?** Через прокси. Spring оборачивает бин, и при внешнем вызове TransactionInterceptor открывает транзакцию через TransactionManager, вызывает метод и делает commit или rollback. Транзакция привязана к потоку через ThreadLocal.
- **Почему не работает вызов метода изнутри класса?** Вызов `this.method()` идёт напрямую к объекту, минуя прокси, поэтому аннотация не срабатывает. Решения: вынести метод в отдельный бин, внедрить себя через прокси или использовать TransactionTemplate.
- **Откатится ли транзакция на checked-исключении?** По умолчанию нет — откат только на RuntimeException и Error. Нужно `rollbackFor = Exception.class` или своё непроверяемое исключение.
- **Чем REQUIRED отличается от REQUIRES_NEW?** REQUIRED присоединяется к существующей транзакции — если внутри что-то упадёт, откатится всё. REQUIRES_NEW приостанавливает внешнюю и открывает свою — например, чтобы записать аудит, даже если основная операция откатится. Цена — второе соединение с базой.
- **Что даёт readOnly = true?** Подсказку: Hibernate не делает dirty checking и flush, драйвер может отправить запрос на реплику. Это не запрет записи на уровне базы — зависит от драйвера и базы.

### Ловушки

- Аннотация на приватном методе молча ничего не делает (проверь для своей версии Spring, какие модификаторы поддерживаются).
- Исключение поймали внутри метода и не пробросили — транзакция зафиксируется.
- Долгий внешний вызов (HTTP, Kafka) внутри транзакции держит соединение из пула — под нагрузкой пул кончается.
- `@Transactional` на методе, который отправляет сообщение в Kafka: сообщение уйдёт, даже если транзакция потом откатится. Нужен outbox или транзакционный продюсер.

### Из вашего опыта

В индексаторе вы писали события пачками. Хороший рассказ: почему пачка пишется в одной транзакции, что будет при падении посреди пачки и как вы обеспечивали идемпотентность повторной записи.

### Проверь себя

- **Какой класс Spring реально открывает транзакцию?** TransactionInterceptor, через PlatformTransactionManager.
- **Будет ли транзакция в @Async-методе, вызванном из транзакционного?** Своей — только если у @Async-метода есть @Transactional; внешняя не переходит, она в другом потоке.
- **Как записать аудит, даже если основная операция откатится?** Отдельный бин с REQUIRES_NEW.

### Источники

- Spring Framework Reference — Transaction Management (проверь перед собесом раздел про propagation для своей версии).
```
