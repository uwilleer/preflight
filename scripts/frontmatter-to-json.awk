#!/usr/bin/awk -f
# Parse a restricted YAML frontmatter into JSON.
# Supports keys with: plain string, quoted string, or bracketed list [a, b, c].
# Not a full YAML parser — only the fields preflight uses.

BEGIN {
  in_fm = 0
  fm_done = 0
  n = 0
}

/^---[[:space:]]*$/ {
  if (!in_fm && !fm_done) { in_fm = 1; next }
  if (in_fm) { in_fm = 0; fm_done = 1; next }
}

in_fm {
  # key: value  — split on first colon
  idx = index($0, ":")
  if (idx == 0) next
  key = substr($0, 1, idx - 1)
  val = substr($0, idx + 1)
  sub(/^[[:space:]]+/, "", key)
  sub(/[[:space:]]+$/, "", key)
  sub(/^[[:space:]]+/, "", val)
  sub(/[[:space:]]+$/, "", val)
  # strip trailing inline comment
  sub(/[[:space:]]+#.*$/, "", val)
  if (key == "" || val == "") next
  keys[++n] = key
  vals[n]  = val
}

END {
  if (n == 0) exit 0
  printf "{"
  for (i = 1; i <= n; i++) {
    printf "%s\"%s\":%s", (i > 1 ? "," : ""), keys[i], to_json(vals[i])
  }
  printf "}"
}

function to_json(v,   s, arr, a, i, out) {
  # bracketed list
  if (v ~ /^\[.*\]$/) {
    s = substr(v, 2, length(v) - 2)
    gsub(/[[:space:]]+$/, "", s)
    gsub(/^[[:space:]]+/, "", s)
    if (s == "") return "[]"
    n_arr = split(s, arr, /[[:space:]]*,[[:space:]]*/)
    out = "["
    for (i = 1; i <= n_arr; i++) {
      a = arr[i]
      sub(/^"/, "", a); sub(/"$/, "", a)
      sub(/^'\''/, "", a); sub(/'\''$/, "", a)
      out = out (i > 1 ? "," : "") escape_str(a)
    }
    return out "]"
  }
  # quoted string
  if (v ~ /^".*"$/) {
    s = substr(v, 2, length(v) - 2)
    return escape_str(s)
  }
  # plain string
  return escape_str(v)
}

function escape_str(s) {
  gsub(/\\/, "\\\\", s)
  gsub(/"/,  "\\\"", s)
  gsub(/\t/, "\\t",  s)
  gsub(/\n/, "\\n",  s)
  gsub(/\r/, "\\r",  s)
  return "\"" s "\""
}
