<p>a <<< b</p>
<?php
function f() {
    return 1;
}
<?php
function & foo() {
    return $x;
}
function &bar() {
    return $y;
}
<?php
function a() {
    $t = <<<	EOT
{
EOT;
    return $t;
}
function b() {
    return 1;
}
<?php
function a() {
    $t = <<<A€
{
A€;
    return $t;
}
function b() {
    return 1;
}
<?php
function a() {
    $t = <<<EOT
EOT€ {
EOT;
    return $t;
}
function b() {
    return 1;
}
<?php
function a() {
    $t = 'x' .
        EOT . <<<EOT
x
{
EOT;
    return $t;
}
function b() {
    return 1;
}
