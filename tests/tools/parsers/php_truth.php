<?php
// The named functions and methods PHP's own tokenizer finds in a repo's PHP files, with a body, as JSON:
// {path: [[name, first line, last line], ...]}. Usage: php php_truth.php REPO FOLDER
$repo = $argv[1]; $sub = $argv[2]; $out = [];
$it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator("$repo/$sub", FilesystemIterator::SKIP_DOTS));
foreach ($it as $f) { if (substr($f, -4) !== '.php') continue;
  $tokens = @token_get_all(file_get_contents($f)); $rows = []; $n = count($tokens);
  for ($i = 0; $i < $n; $i++) { $t = $tokens[$i];
    if (is_array($t) && $t[0] === T_FUNCTION) { $j = $i + 1; while ($j < $n && is_array($tokens[$j]) && in_array($tokens[$j][0], [T_WHITESPACE])) $j++;
      if ($j < $n && $tokens[$j] === '&') { $j++; while ($j < $n && is_array($tokens[$j]) && $tokens[$j][0] === T_WHITESPACE) $j++; }
      if (!($j < $n && is_array($tokens[$j]) && $tokens[$j][0] === T_STRING)) continue; $name = $tokens[$j][1]; $line = $t[2];
      // find body: first { or ; at paren depth 0
      $depth = 0; $k = $j; $line_now = $line; $end = null; $braces = 0; $started = false;
      for (; $k < $n; $k++) { $x = $tokens[$k]; if (is_array($x)) { $line_now = $x[2] + substr_count($x[1], "\n"); if (in_array($x[0], [T_CURLY_OPEN, T_DOLLAR_OPEN_CURLY_BRACES])) { $braces++; } continue; }
        if ($x === '(') $depth++; elseif ($x === ')') $depth--; elseif ($x === ';' && !$started && $depth === 0) break;
        elseif ($x === '{') { $braces++; $started = true; } elseif ($x === '}') { $braces--; if ($started && $braces === 0) { $end = $line_now; break; } } }
      if ($end !== null) $rows[] = [$name, $line, $end]; } }
  $out[substr($f, strlen($repo) + 1)] = $rows; }
echo json_encode($out);
