import os
import datetime
import time

import click
import requests
import smtplib, ssl

DISABLE_EMAIL = os.environ.get("ENABLE_EMAIL", True)
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
RETRY_SPAN = 300

with open('centers.txt') as centers_txt:
    centers = centers_txt.readlines()
centers = [center.strip() for center in centers
           if not center.startswith("#")]


def checkVaccine(motive, vaccines):
    vac_check = False
    for vaccine in vaccines:
        if vaccine in motive.lower():
            vac_check = True
    return vac_check


def checkAppointments(vaccines):
    for center in centers:
        nb_availabilities = 0
        response = requests.get(f"https://www.doctolib.de/booking/{center}.json")
        data = response.json()["data"]
        bookingurl =  (f"https://www.doctolib.de/booking/{center}")
        visit_motives = [visit_motive for visit_motive in data["visit_motives"]
                         if (visit_motive["name"].startswith("Erstimpfung")
                         or visit_motive["name"].startswith("Einzelimpfung"))
                         and checkVaccine(visit_motive["name"], vaccines)]
        if not visit_motives:
            click.echo(click.style(f"{data['profile']['name_with_title']}: bietet keine entsprechenden Impfungen an", fg='red'))
            continue

        places = [place for place in data["places"]]
        if not places:
            continue
        for place in places:
#            for motive in visit_motives:
                start_date = datetime.datetime.today().date().isoformat()
                visit_motive_ids = [motive["id"] for motive in visit_motives]
                practice_ids = place["practice_ids"][0]
                place_name = place["formal_name"] if len(place["formal_name"])>0 else data['profile']['name_with_title']
                place_address = place["full_address"]

                agendas = [agenda for agenda in data["agendas"]
                           if agenda["practice_id"] == practice_ids and
                           not agenda["booking_disabled"] and
                           any(x in visit_motive_ids for x in agenda["visit_motive_ids"])]
#                           any(x in a for x in b)
#                           visit_motive_ids in agenda["visit_motive_ids"]]
                if not agendas:
                    print("not agenda")
                    continue

                agenda_ids = "-".join([str(agenda["id"]) for agenda in agendas])

                # print(visit_motive_ids)
                # print(practice_ids)
                # print(agenda_ids)
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
                response = requests.get(
                    "https://www.doctolib.de/availabilities.json",
                    params={
                        "start_date": start_date,
                        "visit_motive_ids": visit_motive_ids,
                        "agenda_ids": agenda_ids,
                        "practice_ids": practice_ids,
                        "insurance_sector": "public",
                        "destroy_temporary": "true",
                        "limit": 2
                    }, headers=headers
                )
                response.raise_for_status()
#                print(response.json())
                nb_availabilities = response.json()["total"]
# show availabilities
                result = f"{str(nb_availabilities)} Termin(e) verfügbar bei {place_name}, {place_address}{os.linesep+bookingurl if nb_availabilities > 0 else ''}"
                if (nb_availabilities>0):
                    click.echo(click.style(result, fg='green'))
                else:
                    click.echo(result)
    if nb_availabilities > 0 and DISABLE_EMAIL != "true":
                    context = ssl.create_default_context()
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                        server.login(SENDER_EMAIL, SENDER_PASSWORD)
                        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, result.encode('utf-8'))
                        print("  --> Alert sent to " + RECEIVER_EMAIL)

def selectVaccines():
    with open('vaccines.txt') as vaccines_txt:
        vaccines = vaccines_txt.readlines()
    vaccines = [vaccine.strip().lower() for vaccine in vaccines]
    for i, vaccine in enumerate(vaccines):
        click.echo(f"{i}. {vaccine}")
    click.echo(f"{len(vaccines)}. alle Impfstoffe"),
    choice = click.prompt(
        "Bitte wählen:",
        type=click.Choice([str(i) for i in range(len(vaccines) + 1)]),
        show_default=False,
        default='0'
    )
    choice = int(choice)
    useVacs = []
    if choice == len(vaccines):
        useVacs = vaccines
    else:
        useVacs.append(vaccines[choice])
    return useVacs

# Go
vaccines = selectVaccines()
while True:
    checkAppointments(vaccines)
    print("Nächster Versuch in 5 Minuten")
    if RETRY_SPAN==0:
        continue
    time.sleep(RETRY_SPAN)