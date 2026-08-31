Ad Age covered this as a case study during Cannes. For Google's AI Lighthouse
program, Tombras was asked to build an out-of-home campaign for PODS that would
have been impractical before generative AI. We turned a PODS moving truck into a
billboard whose message changed with its location and with real-time context as
it drove through New York City.

<dl class="facts">
  <dt>My role</dt><dd>Chief Technology Officer, Tombras. The API and cloud system behind the truck</dd>
  <dt>Technology</dt><dd>Google Gemini, Vertex AI, Maps, Sheets and Cloud Run</dd>
  <dt>Recognition</dt><dd>2025 Webby for Best Experiential Design, AI Immersive &amp; Games</dd>
</dl>

## How it worked

The system had to do three things at once: know where the truck was, decide what
was worth saying in that specific neighbourhood, and get the line onto the
display before the truck had moved on. As I put it to Think with Google, "we
built an API that was able to combine all the headline data plus all the
real-time data and then provide it back to the truck to display."

That sounds simple and it is not. The interesting engineering was never the
model call. It was latency, the shape of the data, what happens when a request
fails halfway down Broadway, and how you keep thousands of generated lines
inside a brand voice without a human approving each one in the moment.

## What it produced

Think with Google reported that the campaign generated 6,000 lines of copy, and
that the truck travelled through 299 neighbourhoods in 29 hours. They also
reported a 60% increase in PODS website sessions and a 33% increase in quote
requests in New York City.

## Why it mattered

This was not AI replacing creative work. The creative team set the voice, wrote
the premise and chose the strongest outputs; the system made it possible to
operate at a scale that would otherwise have needed thousands of manual
executions. One of the copywriters told Think with Google he would "personally
never agree to writing 6,000 lines", which is exactly the point. The machine
did the volume. People decided what was worth saying.

I keep coming back to that division of labour. It is the same one I argued for
at [El Ojo de Iberoamérica](/work/ojo3/), and the reason I think
[human creativity still leads](/work/human/) even as the tooling gets better.

Google went on to use the campaign in its own advertising for Gemini, which is
[its own entry](/work/pods/).
