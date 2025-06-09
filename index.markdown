---
layout: default
title:  "jtubert.com"
date:   2025-06-08 11:16:09 -0400
---

{% comment %}
  {% include story-loop.html file="story4.html" %}
{% endcomment %}

{% include story-loop.html file='story1.html' %}

{% for story in site.data.stories %}
  {% include gridlayer.html 
    id=story.id
    category=story.category 
    title=story.title 
    date=story.date 
    link=story.link
    asset=story.asset
    type=story.type 
  %}
{% endfor %}








