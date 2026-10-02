# The Problem Domain

In both cases we had code that solves one specific problem for a very diverse set of types:

* a serialization library, used by all Ceph code that needs to write data to disk or to the network
* Lua bindings, that expose many different internal types to scripts running inside one of the Ceph daemons

Concepts let us organize these types from the point of view of what we do with them:

| we ask                                   | the concept             |
|------------------------------------------|-------------------------|
| can it be exposed to a script?           | `lua_metatable`         |
| can it be serialized? how?               | `encodable`, `raw_bytes`, `self_encoding` |
| can it be looked up without a temporary? | `finds_by_string_view`  |
| is it safe to iterate statelessly?       | `unique_keys`           |

* The class hierarchy says what a type **is**. A concept says what we can **do** with it.
* The types did not change. No base class was added, no type was touched.

---

## Slide 7.1 (Backup): So, What Are Concepts Good For?

1. More readable errors - true, and the least important
2. Overload resolution that you can read and extend
3. Picking the faster implementation, per type, at no cost to the caller
4. Turning a runtime bug into code that does not compile
5. ~~giving cool talks in C++ conferences~~ - you be the judge

Where to look in your own code base: a template that is used with many unrelated types, and has a comment that explains what the type must provide.

> Notes: backup slide. It mirrors the first slide and walks the same list:
> errors, overload resolution, performance, correctness.
