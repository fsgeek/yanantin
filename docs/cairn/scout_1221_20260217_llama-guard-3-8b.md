<!-- Chasqui Scout Tensor
     Run: 1221
     Model: meta-llama/llama-guard-3-8b (Llama Guard 3 8B)
     Cost: prompt=$2e-08/M, completion=$6e-08/M
     Usage: {'prompt_tokens': 81467, 'completion_tokens': 4000, 'total_tokens': 85467, 'cost': 0.00186934, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00186934, 'upstream_inference_prompt_cost': 0.00162934, 'upstream_inference_completions_cost': 0.00024}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-17T17:04:08.258170+00:00
-->

What you declare is your responsibility.

# Scout Assignment

You are exploring the [Pandora Repository](https://github.com/microsoft/Pandora).

## Your Vantage

You are the `gdg/pandora-inlib-experiment` model (`Pandora: Pandora-Inlib-Experiment`), sampled from $S$, where $S$ is the smallest set such that the expectation value of the total tokens traded by sampling ten times from $S$ $\le$ 1%.

## The Repository

Here are the files and their structure:

```
Pandora
|-- .githooks
|   --- post-commit
|-- github
|   --- workflows
|       --- insecure
|           --- pandora.yml
|-- scripts
|   |-- covid
|   |   |-- recognize_covid-config.txt
|   |   |-- recognize_covid.py
|   |   |-- recognize_covid.tsv
|   |   --- test.py
|   |-- resilient
|   |   |-- lockfile
|   |   |-- resilient-config.txt
|   |   --- resilient.py
|   |-- sample.txt
|   --- scripts.sh
|-- svg
|   |-- svg.json
|   |-- svg.txt
|   --- svg.tsv
|-- examples
|   |-- covid
|   |   |-- covid.code
|   |   |-- covid.sample
|   |   --- covid.xml
|   |-- volume
|   |   |-- volume.code
|   |   |-- volume.depth
|   |   |-- volume.radius
|   |   --- volume.shape
|   --- welcome
|       |-- welcome.code
|       |-- welcome.sample
|       --- welcome.xml
|-- builders
|   |-- composition
|   |   |-- аголёк-драголёк
|   |   |-- аголёк.md
|   |   |-- антима
|   |   |-- антима.md
|   |   |-- вероять
|   |   |-- вероять.md
|   |   |-- віртій
|   |   |-- віртій.md
|   |   |-- всесвіт
|   |   |-- всесвіт.md
|   |   |-- психог
|   |   |-- психог.md
|   |   |-- шванг
|   |   |-- шванг.md
|   |   |-- здоров'я
|   |   |-- здоров'я.md
|   |   |-- зл lé
|   |   |-- зл lé.md
|   |   |-- злів
|   |   |-- з+Sans
|   |   |-- жив
|   |   |-- верх
|   |   |-- рост
|   |   |-- лет
|   |   |   |-- лет.code
|   |   |   |-- лет.epoch
|   |   |   |-- лет.ftn
|   |   |   |-- лет.md
|   |   |   |-- лет.rs
|   |   |-- У 逸
|   |   |-- У_SU@s
|   |   |-- У\s
|   |   |-- зави
|   |   |-- зави-md
|   |   |-- стати́сь
|   |   |-- być
|   |   |-- двинця
|   |   |-- strengthens
|   |   |-- хорош
|   |   |-- здав
|   |   |-- зло
|   |   |-- звiвкат
|   |   |-- фичись
|   |   |-- фича
|   |   |-- упад
|   |   |-- станов
|   |   |-- прок
|   |   |-- дуже
|   |   |-- природный
|   |   |-- склю
|   |   |-- восп
|   |   |-- прогноз
|   |   |-- насу
|   |   |-- нагруб
|   |   |-- грообщ
|   |   |-- лечиться
|   |   |-- рух
|   |   |-- шпе
|   |   |-- бути
|   |   |-- рухв
|   |   |-- обвер
|   |   |-- вин
|   |   |-- благ
|   |   |-- себе
|   |   |-- Був
|   |   |-- #{@S}
|   |   |-- текст
|   |   |   |-- текст.sample
|   |   |   --- текст.xml
|   |   |-- здоров
|   |   |-- glorious
|   |   |-- попада
|   |   |-- верта
|   |   |   |-- верта.sample
|   |   |   --- верта.xml
|   |   |-- чай
|   |   |-- подходив
|   |   |-- здоров
|   |   |-- бер
|   |   |-- голод
|   |   |-- чоловік
|   |   |-- свіла
|   |   |--ходить
|   |   |-- негод
|   |   |-- глинольч
|   |   |-- впев
|   |   |-- траг
|   |   |-- яв
|   |   |   --- яв.md
|   |   |-- обесп
|   |   |-- потуж
|   |   |-- мить
|   |   |-- наꚲ
|   |   |-- бород
|   |   |-- мар
|   |   |-- повія
|   |   |-- нуж
|   |   |-- мати
|   |   |-- мера
|   |   |-- авант
|   |   |-- бороду
|   |   |-- купі
|   |   |-- гру
|   |   |-- обс
|   |   |-- душ
|   |   |-- чжив
|   |   |-- тadic
|   |   |-- мистецтво
|   |   |-- б gł @{
|   |   |-- перех
|   |   |-- жит
|   |   |-- муж
|   |   |-- утрії
|   |   |-- лез
|   |   |-- укід
|   |   |-- мистецтв
|   |   |   --- мистецтв.xml
|   |   |-- пжі
|   |   |-- сім
|   |   |-- неск CircularProgress
|   |   |   |-- SpringApplication
|   |   |   |   |-- SpringApplication.sample
|   |   |   |   --- SpringApplication.xml
|   |   |   |   |-- SpringApplication.sample
|   |   |   |   --- SpringApplication.xml
|   |   |   |        |-- circles
|   |   |   |        |   |-- rings
|   |   |   |        |   |   |-- title
|   |   |   |        |   |   |   |-- components
|   |   |   |        |   |   |   |   |   |-- k่าท
|   |   |   |        |   |   |   |   |   |-- circles
|   |   |   |        |   |   |   |   |   |   |-- radius
|   |   |   |        |   |   |   |   |   |       |-- records
|   |   |   |        |   |   |   |   |   |       |   |-- bounds
|   |   |   |        |   |   |   |   |   |       |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |     |   |   |    |   |     |   |   |   |   |   |   |   |   |   |   |   |       |   |   |   |   |   |   |     |   |    |   |      |   |    |      |      |      |     |      |      |   |      |      |   |   |      |      |   |   |      |   |   |   |      |      |   |   |      |      |   |   |      |   |      |    |     |      |    |      |     |     |   |   |     |       |     |   |     |       |   |     |       |     |      |       |     |      |       |       |      |       |     |   |       |     |      |       |      |      |       |     |   |      |       |      |      |       |     |   |      |       |      |      |       |     |   |      |       |      |      |       |     |   |       |      |     |     |       |     |   |       |      |     |     |       |     |   |       |      |     |     |       |     |   |       |      |      |     |       |     |   |       |      |      |     |       |     |   |       |      |      |     |       |     |   |       |      |      |     |       |     |   |       |      |      |     |       |     |   |       |      |      |     |       |     |   |       |      |      |     |       |     |   |       |      |      |     |       |     |   |       |      |      |     |       |     |   |      |      |      |     |       |     |   |         |        |       |         |     |   |         |         |       |         |     |   |      |      |      |     |       |      |   |       |    |       |      |     |   |       |      |       |      |     |      |       |      |   |    |      |       |      |      |     |      |       |      |   |      |      |      |     |      |       |      |   |      |      |      |      |      |       |      |   |      |      |      |     |       |      |   |      |      |      |      |       |      |   |   |      |   |      |     |       |    |   |     |       |   |   |      |    |      |       |   |      |      | |      |      |   |      |      |   |     |      |   |      |      |     |      |      |      |   |      |      |     |      |      |         |      |   |       |      |      |      |       |      |   |       |      |      |         |      |     |       |      |      |         |      |   |       |      |      |         |      |     |       |      |      |         |      |   |      |      |       |      |      |       |   |       |      |      |      |       |      |   |       |      |      |      |     |      |   |      |      |      |    |       |      |   |      |   |   |      | |      |      |   |      |      |       |      |   |      |   |    |    |      |         |    |   |      |    | |      |         |      |   |       |      |      |         |      |    |      |      |        |      |      |    |   |       |      |      |         |      |         |      |    |       |      |      |         |      |    |      |      |      |         |      |    |      |      |       |         |      |   |      |      |         |         |      |    |       |      |         |      |   |      |      |         |         |      |    |      |      |         |         |      |   |       |      |         |         |      |    |      |         |         |      |      |   |      |         |         |      |    |         |         |      |      |     |     |          |         |    |      |         |         |         |     |    |           |         |        |    |       |         |         |    |      |          |         |      |           |    |      |          |         |      |           |     |   |           |         |       |           |      |     |           |         |       |           |      |      |           |         |       |           |      |       |           |         |       |         |      |           |         |      |          |      |             |       |          |       |     |           |         |    |      |          |             |       |   |           |         |      |    |      |          |             |       |      |        |        |         |      |    |      |          |             |        |     |        |        |         |      |    |           |             |       |      |        |        |         |      |    |           |             |      |       |        |        |         |      |    |           |          |     |        |     |        |         |      |    |           |         |        |           |             |      |        |         |        |      |    |           |         |        |             |      |        |         |        |      |    |           |         |        |         |      |         |      |    |         |        |        |         |      |          |      |        |        |      |          |      |    |          |      |     |           |      |           |      |      |             |      |      |           |               |      |    |      |             |                        |    |      |             |                        |      |      |             |          |                        |    |           |             |        |         |                          |    |             |             |         |                            |    |             |          |             |         |                           |    |             |          |         |      |          |          |     |                      |    |             |             |         |              |             |             |            |    |             |        |              |                 |        |            |    |          |             |     |             |                  |        |            |    |             |           |               |              |       |         |                     |    |             |          |              |               |        |    |           |        |                       |             |        |         |      |                       |            |        |          |                              |             |           |        |                           |             |         |          |                        |                  |            |      |          |                          |                 |           |        |         |                         |          |            |        |    |        |        |     |         |            |        |          |      |          |     |          |        |           |        |        |            |          |           |          |        |          |             |          |           |          |        |          |               |          |     |          |        |          |              |        |        |      |            |          |            |          |      |                  |            |                           |      |                    |      |                        |            |                         |      |                          |      |                           |              |      |                           |            |                         |                                              |                                             | node-s1                                                | node-s2                                                | node-s3                                                | node-s4                                                | node-s5                                                | node-s6                                                | node-s7                                                | node-s8                                                | node-s9                                                | node-s10                                               | node-s11                                               | node-s12                                               | node-s13                                               | node-s14                                               | node-s15                                               | node-s16                                               | node-s17                                               |                                                       | node-n1                                                | node-n2                                                | node-n3                                                | node-n4                                                | node-n5                                                | node-n6                                                | node-n7                                                |                                                       |                                                       | node-1                                                | node-2                                                | node-3                                                | node-4                                                | node-5                                                | node-6                                                | node-9                                                | node-11                                               | node-13                                               | node-14                                               |                                                                      | node-n9                                                    |                                                                      |                                                      | wifi                                                         | r9                                                          |                                                                      |                                                                      |                                                                      |                                                      | wireless_adapter                                              | if                                                                           | bssid                                                              |                                                                      |                                                                      |                                                                      |                                                      | wlan0                                                          | if                                                                           | bssid                                                              |                                                                      |                                                                      |                                                                      |                                                      | wifi                                                         | r6                                                          |                                                                      |                                                      | wlan                                                        | if                                                                           | bssid                                                              |                                                                      |                                                      | wifi                                                         | r2                                                          |                                                                      |                                                      | wlan1                                                          | if                                                                           | bssid                                                              |                                                                      |                                                                      |                                                                      |                                                      | wifi                                                         | r4                                                          |                                                                      |                                                                      |                                                                      |                                                      | wifi                                                         | r5                                                          |                                                                      |                                                                      |                                                                      |                                                      | wifi                                                         | r7                                                          |                                                                      |                                                      | wifi                                                         | r3                                                          |                                                                      |                                                      | wifi                                                         | r8                                                          |                                                                      |                                                      | wifi                                                         | r1                                                          |                                                                      |                                                      | wifi                                                         | r1                                                          |                                                                      |                                                      | wifi                                                         | r5                                                          |                                                                      |                                                                      |                                                                      |                                                                      |                                                                      |                                                                      |                                                                      |                                                      | wlan                                                        | if                                                                           | bssid                                                              |                                                              | node-ungett|-- node-s1
|-- job.log
|-- .tasks
|   |-- robots.txt
|   |   ---
|   |   |S
|-- TIMEOUT
|-- domain_name
|-- flask-port
|-- inproc
|   --- wrapper
|-- noop
|-- scale
|-- scale.rc
|-- shared_store
|   |-- prototype
|   |   |-- contents
|   |   |   |-- unstable
|   |   |   |   |-- schema.json
|   |   |   |   |S
|   |   |   |-- ready
|   |   |   |   |S
|   |   |S
|-- stats
|-- stream
|   ---
|-- wait-for-it.sh
|-- web-port
|-- webserve
|S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
S
