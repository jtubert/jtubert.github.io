---
layout: default
title:  "jtubert.com"
date:   2025-06-08 11:16:09 -0400
---

{% comment %}
  {% include story-loop.html file="webby_sweet.html" %}
{% endcomment %}



{% assign stories = "story1.html,story101.html,webby_pods.html,webby_sweet.html,adage.html,freezerflag.html,latinspots.html,pods.html,story2.html,story3.html,story4.html,story5.html,story6.html,story7.html,story8.html,story9.html,story10.html,story11.html,story12.html,story13.html,story14.html,story15.html,story16.html,story17.html,story18.html,story19.html,story20.html" | split: "," %}

{% for story in stories %}
  {% include story-loop.html file=story %}
{% endfor %}







