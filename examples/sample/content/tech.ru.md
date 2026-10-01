---
stage: tech
sources: [kafka-docs]
last_verified: 2026-09-30
---

@@ tech.services.messaging
Консьюмеры читают топик партициями. Если они не успевают за продюсером, растёт лаг.

@@ tech.services.consistency
Между сервисами согласованность в конечном счёте. Цена — устаревшие данные на чтении.

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

```java
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

```
### Вопросы на интервью

- **Как работает @Transactional?** Через прокси. Spring оборачивает бин, и при внешнем вызове TransactionInterceptor открывает транзакцию через TransactionManager, вызывает метод и делает commit или rollback. Транзакция привязана к потоку через ThreadLocal.
- **Почему не работает вызов метода изнутри класса?** Вызов `this.method()` идёт напрямую к объекту, минуя прокси, поэтому аннотация не срабатывает. Решения: вынести метод в отдельный бин, внедрить себя через прокси или использовать TransactionTemplate.
- **Откатится ли транзакция на checked-исключении?** По умолчанию нет — откат только на RuntimeException и Error. Нужно `rollbackFor = Exception.class` или своё непроверяемое исключение.
- **Чем REQUIRED отличается от REQUIRES_NEW?** REQUIRED присоединяется к существующей транзакции — если внутри что-то упадёт, откатится всё. REQUIRES_NEW приостанавливает внешнюю и открывает свою — например, чтобы записать аудит, даже если основная операция откатится. Цена — второе соединение с базой.
- **Что даёт readOnly = true?** Подсказку: Hibernate не делает dirty checking и flush, драйвер может отправить запрос на реплику [verify] — зависит от драйвера и настройки маршрутизации, в документации Spring этого нет. Это не запрет записи на уровне базы — зависит от драйвера и базы.

### Ловушки

- Аннотация на приватном методе молча ничего не делает. С Spring 6.0 при прокси на классах (CGLIB) работают и `protected`, и package-private методы; при прокси на интерфейсах — только `public` из интерфейса.
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

- [Spring Framework Reference — Using @Transactional](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/annotations.html)
- [Spring Framework Reference — Transaction Propagation](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/tx-propagation.html)
- [Spring Framework Reference — Rolling Back a Declarative Transaction](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/rolling-back.html)
- [Spring Boot Reference — Aspect-Oriented Programming](https://docs.spring.io/spring-boot/reference/features/aop.html)
