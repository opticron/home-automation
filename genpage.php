<?php
$args = array();
try {
  foreach($_GET as $key=>$val) { 
      $args[] = $key . "=" . $val;
  }
} catch (Exception $e) {
}
passthru("QUERY_STRING='".join("&",$args)."' python /var/www/openmediavault/genpage.py");
?>
