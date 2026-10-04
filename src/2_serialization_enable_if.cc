// Use case 2, before: overload resolution with enable_if.
//
//   (default)        compiles and runs
//   -DFORGOT_NOT     drop the '!' from the vector overload: ambiguous call
//   -DNOT_ENCODABLE  encode a type that has no encode()

#include <cstdint>
#include <cstdio>
#include <list>
#include <type_traits>
#include <utility>
#include <vector>

#include "bufferlist.h"

// primary template: "no"
template <typename T, typename = void>
struct has_encode : std::false_type {};

// specialization: "yes", but only if v.encode(bl) compiles
template <typename T>
struct has_encode<T, std::void_t<decltype(
    std::declval<const T&>().encode(std::declval<bufferlist&>()))>>
  : std::true_type {};

// numbers: copy the bytes
template <typename T>
std::enable_if_t<std::is_arithmetic_v<T>>
encode(const T& v, bufferlist& bl) {
  bl.append(&v, sizeof(v));
}

// classes that know how to encode themselves
template <typename T>
std::enable_if_t<has_encode<T>::value>
encode(const T& v, bufferlist& bl) { v.encode(bl); }

// vector of anything: one element at a time
template <typename T, typename A>
#ifdef FORGOT_NOT
std::enable_if_t<true>
#else
std::enable_if_t<!std::is_arithmetic_v<T>>  // <-- note the ! sign
#endif
encode(const std::vector<T, A>& v, bufferlist& bl) {
  encode(uint32_t(v.size()), bl);
  for (const auto& e : v) encode(e, bl);
}

// vector of numbers: one copy
template <typename T, typename A>
std::enable_if_t<std::is_arithmetic_v<T>>
encode(const std::vector<T, A>& v, bufferlist& bl) {
  encode(uint32_t(v.size()), bl);
  bl.append(v.data(), v.size() * sizeof(T));
}

// ... and again for every other container: here is list
template <typename T, typename A>
void encode(const std::list<T, A>& l, bufferlist& bl) {
  encode(uint32_t(l.size()), bl);
  for (const auto& e : l) encode(e, bl);
}

struct Bucket {
  uint64_t id;
  void encode(bufferlist& bl) const { ::encode(id, bl); }
};

struct Tenant { uint64_t id; };            // no encode()

int main() {
  bufferlist bl;
  encode(42, bl);
  encode(Bucket{1}, bl);
  encode(std::vector<int>{1, 2, 3}, bl);
  encode(std::vector<Bucket>{{1}, {2}}, bl);
  encode(std::list<std::vector<Bucket>>{{{1}}, {{2}, {3}}}, bl);
#ifdef NOT_ENCODABLE
  encode(std::vector<Tenant>{}, bl);
#endif
  std::printf("encoded %zu bytes\n", bl.bytes.size());
}
