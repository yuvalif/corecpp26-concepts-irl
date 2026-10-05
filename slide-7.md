# The Problem Domain

Solves one specific problem for a very diverse set of types:

## a serialization library
used by all Ceph code that needs to write data to disk or network

## Lua bindings
expose internal types to scripts running inside Ceph's Object Store frontend

---

## Slide 7.1: Non-Intrusive Solution
<br>
#### The class hierarchy says what a type ***is***. A concept says what we can ***do*** with it
<br>
#### The types did not change. No base class was added. No type was touched

