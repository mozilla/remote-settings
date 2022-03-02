# TODO:
# What logging is not captured in this diagram
# fluentd, which pushes to bigquery
# Stackdriver?
# Public, Writer,
# Statsd sends metrics to influxdb. Grafana instance
# S3 bucket for lambda(s)?

workspace "Remote Settings" "Remote Settings Service" {
    model {
      firefox = softwaresystem "Firefox" "" "Web Browser"
      sentry = softwaresystem "Sentry" "3rd party logging service" "External System, Logging"
      stackdriver = softwaresystem "Stackdriver" "GCP Logging Service" "External System, Logging"
      experimenter = softwaresystem "Experimenter" "" "External System"
      normandy = softwaresystem "Normandy" "manages recipes of changes to make to Firefox" "External System"
      autograph = softwaresystem "Autograph" "cryptographic signature service that implements Content-Signature, XPI Signing for Firefox web extensions, MAR Signing for Firefox updates, APK V1 Signing for Android, PGP, GPG2 and RSA." "External System"
      megaphone = softwaresystem "Megaphone" "Provides global broadcasts for Firefox" "External System"
      remoteSettings = softwaresystem "Remote Settings" "Manages evergreen settings data in Firefox" {
        remoteSettingsReader = container "Remote Settings Reader" "" "Python, Kinto Server" "Logging"
        remoteSettingsWriter = container "Remote Settings Writer" "" "Python, Kinto Server" "Logging"
        lambdas = container "Remote Settings Lambdas" "" "AWS Lambda" "Logging" {
          # Backport records config
          # https://github.com/mozilla-services/cloudops-deployment/blob/dbb19a8373fe061ba65fe9610845a901a3535943/projects/kinto-lambda/ansible/envs/default.yml
          # arbitrary number of this lambda. How do we represent this?
          backport_records = component "backport_records" "Backport records creations, updates and deletions from one collection to another" "AWS Lambda/ cron job"
          sync_megaphone = component "sync_megaphone" "Read latest timestamp from monitor/changes & updates it in Megaphone if outdated." "AWS Lambda / cron job"
          refresh_signature = component "refresh_signature" "Rotate signature and certificates of collections." "AWS Lambda / cron job"
        }
        database = container "Remote Settings Database" "Storage, cache, and permissions" "Postgres Database" "Database"
        mainCDN = container "Main CDN" "" "AWS Cloudfront" "Database"
        attachmentsCDN = container "Attachments CDN" "" "AWS Cloudfront" "Database"
        blocklistCDN = container "Blocklist CDN" "" "AWS Cloudfront" "Database"
        attachmentsBucket = container "Attachments Bucket" "" "S3 Bucket" "Storage"
        blocklistDummyBucket = container "Blocklist Dummy Bucket" "Bucket required by blocklistCDN" "S3 Bucket" "Storage"
        loggingBucket = container "Logging Bucket" "" "S3 Bucket" "Storage"
        cloudwatch = container "Cloudwatch" "" "AWS Cloudwatch"
      }

      megaphone -> firefox "Pushes RS data" "HTTPS"
      mainCDN -> remoteSettingsReader "Forwards requests" "HTTPS"
      attachmentsCDN -> attachmentsBucket "Forwards requests" "HTTPS"
      blocklistCDN -> blocklistDummyBucket "" ""
      remoteSettingsReader -> database "Reads collections" "Postgres Protocol/SSL"
      remoteSettingsWriter -> database "Reads from and writes to" "Postgres Protocol/SSL"
      remoteSettingsWriter -> attachmentsBucket "Writes attachments" "HTTPS"
      remoteSettingsWriter -> autograph "Send serialized collection data to receive content signature" "HTTPS"

      # Logging
      ## Reader / Writer
      remoteSettingsWriter -> sentry "Writes logs" "HTTPS" "Logging"
      remoteSettingsReader -> sentry "Writes logs" "HTTPS" "Logging"
      remoteSettingsWriter -> stackdriver "Writes logs" "HTTPS" "Logging"
      remoteSettingsReader -> stackdriver "Writes logs" "HTTPS" "Logging"
      ## lambdas
      lambdas -> sentry "Writes logs" "HTTPS" "Logging"
      lambdas -> cloudwatch "Writes logs" "HTTPS" "Logging"
      ## CDNs
      mainCDN -> loggingBucket "Writes Logs" "HTTPS" "Logging"
      attachmentsCDN -> loggingBucket "Writes Logs" "HTTPS" "Logging"
      blocklistCDN -> loggingBucket "Writes Logs" "HTTPS" "Logging"

      # Lambdas
      lambdas -> remoteSettingsWriter "Run refresh_signature & backport_records jobs"
      lambdas -> mainCDN "GET timestamp from monitor/changes"
      lambdas -> megaphone "PUT broadcast timestamp if outdated"

      sync_megaphone -> mainCDN "GET timestamp from monitor/changes"
      sync_megaphone -> megaphone "PUT broadcast timestamp if outdated"
      refresh_signature -> remoteSettingsWriter "PATCH collections with status=to-refresh"
      backport_records -> remoteSettingsWriter "GET source records, PUT/DELETE destination records"

      live = deploymentEnvironment "Live" {
        deploymentNode "Client Device" {
          firefoxInstance = softwareSystemInstance firefox
        }
        deploymentNode "Sentry" {
          softwareSystemInstance sentry
        }
        deploymentNode "Google Cloud Platform"{
          tags "Google Cloud Platform - Cloud"
          softwareSystemInstance megaphone
          softwareSystemInstance stackdriver
          normandyInstance = softwareSystemInstance normandy
          experimenterInstance = softwareSystemInstance experimenter
        }
        deploymentNode "Amazon Web Services" {
          tags "Amazon Web Services - Cloud"
          softwareSystemInstance autograph
          route53 = infrastructureNode "Route 53" {
            tags "Amazon Web Services - Route 53"
          }
          deploymentNode "Amazon Cloudfront - Main" {
            tags "Amazon Web Services - CloudFront"
            mainCDNInstance = containerInstance mainCDN
          }
          deploymentNode "Amazon Cloudfront - Attachments" {
            tags "Amazon Web Services - CloudFront"
            attachmentsCDNInstance = containerInstance attachmentsCDN
          }
          deploymentNode "Amazon Cloudfront - Blocklist" {
            tags "Amazon Web Services - CloudFront"
            blocklistCDNInstance = containerInstance blocklistCDN
          }
          deploymentNode "Amazon S3 Bucket - Attachments" {
            tags "Amazon Web Services - Simple Storage Service S3 Bucket with Objects"
            containerInstance attachmentsBucket
          }
          deploymentNode "Amazon S3 Bucket - Cloudfront Logs" {
            tags "Amazon Web Services - Simple Storage Service S3 Bucket with Objects"
            containerInstance loggingBucket
          }
          deploymentNode "Amazon S3 Bucket - Blocklist Dummy" {
            tags "Amazon Web Services - Simple Storage Service S3 Bucket with Objects"
            containerInstance blocklistDummyBucket
          }
          deploymentNode "Amazon Virtual Private Cloud"{
            tags "Amazon Web Services - VPC"
            deploymentNode "Amazon EC2 - Writer" {
              tags "Amazon Web Services - EC2"
              containerInstance remoteSettingsWriter
            }
            deploymentNode "Amazon EC2 - Reader" {
              tags "Amazon Web Services - EC2"
              containerInstance remoteSettingsReader
            }
            deploymentNode "Amazon RDS" {
              tags "Amazon Web Services - RDS"
              deploymentNode "AWS Postgres" {
                tags "Amazon Web Services - RDS PostgreSQL instance"
                containerInstance database
              }
            }
            deploymentNode "Amazon Lambdas" {
              containerInstance lambdas
            }
          }
          deploymentNode "Amazon Cloudwatch"{
            tags "Amazon Web Services - CloudWatch"
            containerInstance cloudwatch
          }
        }
        firefoxInstance -> route53 "Requests" "HTTPS"
        route53 -> mainCDNInstance "Forwards requests to"
        route53 -> attachmentsCDNInstance "Forwards requests to"
        route53 -> blocklistCDNInstance "Forwards requests to"
        normandyInstance -> route53 "Sends requests to Writer to CRUD collections"
        experimenterInstance -> route53 "Sends requests to Writer to CRUD collections"
      }
    }

    views {
      component lambdas "RemoteSettingsLambdas"{
        include *
        autolayout lr
      }
      deployment remoteSettings "Live" "CurrentDeployment" {
        include *
        autolayout tb
      }
      deployment remoteSettings "Live" "CurrentDeploymentNoLogging" {
        include *
        exclude "relationship.tag==Logging"
        !script script.groovy
      }
      deployment remoteSettings "Live" "CurrentDeploymentLogging" {
        include *
        exclude "relationship.tag!=Logging"
        !script script.groovy
      }

      themes https://static.structurizr.com/themes/amazon-web-services-2020.04.30/theme.json https://static.structurizr.com/themes/google-cloud-platform-v1.5/theme.json default
      styles {
        element "Google Cloud Platform - Cloud" {
          icon https://www.gend.co/hs-fs/hubfs/gcp-logo-cloud.png?width=730&name=gcp-logo-cloud.png
        }
        element "External System" {
          background #999999
          color #ffffff
        }
        element "Database" {
          shape cylinder
        }
        element "Storage" {
          shape folder
        }
        element "Web Browser" {
          shape WebBrowser
        }
      }
    }

}