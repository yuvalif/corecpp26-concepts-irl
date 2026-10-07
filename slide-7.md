# The Problem Domain

Solves one specific problem for a very diverse set of types:

## a serialization library
Used by all Ceph code that needs to write data to disk or network

## Lua bindings
Expose internal types to scripts running inside Ceph's Object Store frontend

---

## Slide 7.1: Non-Intrusive Solution *(\*)*
<br>
#### The class hierarchy says what a type ***is***.<br>&emsp;&emsp;A concept says what we can ***do*** with it
#### The types did not change.<br>&emsp;&emsp;No base class was added
<br>
<br>
<br>
<br>
<br>
<br>
*(\*) no type was hurt in the making of these slides*

