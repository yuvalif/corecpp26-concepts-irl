// A mock of Ceph's bufferlist: somewhere to append bytes to.
//
// It is a struct and not a plain char* or std::string on purpose: the
// encode() overloads find each other through argument dependent lookup, and
// that needs one argument whose type lives in our own namespace.
#pragma once

#include <cstddef>
#include <string>

struct bufferlist {
  std::string bytes;

  void append(const void* data, std::size_t size) {
    bytes.append(static_cast<const char*>(data), size);
  }
};
