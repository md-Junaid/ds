<!DOCTYPE html>
<html>
  <head>
    <!--  for the browser to show the page in the correct encoding -->
    <meta charset="utf-8">
    <!--  to scale page width automatically -->
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <!-- Meta data for search engines... Not important. -->
    <meta name="description" content="Distributed systems course - TDA596 (Chalmers)">
    <meta name="keywords" content="Lab">
    <meta name="author" content="Beshr Al Nahas">
    <!-- Include the jQuery library. It is used to update the page contents automatically. -->
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.4/jquery.min.js"></script>
    <!-- Inlined javascript code. This could be optionally hosted in another file on the server and included using 'src' attribute as above -->

    <script>
      var page_reload_timeout = 2; //in seconds
      var page_reload_count = 0;
      
      function update_contents(){
        page_reload_count += 1;
        $(".result").remove();
        $("#vote_result_placeholder").load("/result", function (data, status) {
          //alert("Data: " + data + "\nStatus: " + status);
          $("#boardcontents_status_placeholder").text(page_reload_count + ": " + status);
        });
      }

      function reload_countdown(remaining) {
        $("#countdown_placeholder").text("Reloading page in: " + remaining + " seconds.");
        if (remaining <= 0) {
          remaining = page_reload_timeout;
          update_contents();
        }

        setTimeout(function () {
          reload_countdown(remaining - 1);
        }, 1000);
      }

      $(document).ready(function () {
        // reload_countdown(page_reload_timeout);
      });
    </script>

    <title>Byzantine Agreement - TDA596 (Chalmers)</title>
  </head>
  <body>
    <!-- this place will show a count down for the automatic reload of the board contents, downloaded periodically from the server using the javascript function reload_countdown. -->
    <div id="countdown_placeholder"></div>
    <!-- This place shows the status of the auto-reload. 
An error shown here means the server is not responding -->
    <div id="boardcontents_status_placeholder">0: success</div>

    <!-- This is a target for forms to prevent reloading the page on form submit. USE style="display:none" to hide it -->
    <iframe name="noreload-form-target" width="90%" height="50" src="about:blank" frameborder="0" scrolling="yes" resizable seamless></iframe>

    <!-- This place shows the buttons used to request a vote -->
    <div id="vote_form_placeholder">
      <h3>Vote</h3>
      <form id="usrform" target="noreload-form-target">
        <input type="submit" formmethod="post" formaction="/attack" value="Attack" />
        <input type="submit" formmethod="post" formaction="/retreat" value="Retreat" />
        <input type="submit" formmethod="post" formaction="/byzantine" value="Byzantine" />
      </form>

    </div>

    <h3>Result</h3>
    
    <button onclick="update_contents();">Refresh Vote Result</button>

    <div id="vote_result_placeholder">
    <pre>Voting Results ...</pre>
    </div>

  </body>
</html>
