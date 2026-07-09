import React from 'react';
import { Mail, Phone, MapPin, Globe, Linkedin, Github, ExternalLink } from 'lucide-react';
import type {
  ResumeData,
  SectionMeta,
  AdditionalSectionLabels,
} from '@/components/dashboard/resume-component';
import { getSortedSections } from '@/lib/utils/section-helpers';
import { formatDateRange } from '@/lib/utils';
import { SafeHtml } from './safe-html';
import baseStyles from './styles/_base.module.css';
import styles from './styles/murphy.module.css';

interface ResumeMurphyProps {
  data: ResumeData;
  showContactIcons?: boolean;
  additionalSectionLabels?: Partial<AdditionalSectionLabels>;
}

/**
 * Murphy Resume Template
 *
 * Dense professional layout referencing tim-resume-original.pdf:
 * - Full-bleed black header bar: name in large letter-spaced ALL CAPS (white),
 *   mono contact line in light gray.
 * - Gray competency band immediately below the header showing technicalSkills as
 *   pipe-separated items (not repeated in the Additional section at the bottom).
 * - Compact small-caps section headers with a 1px black rule underneath.
 * - Experience entries: bold company + mono dates on one row; italic role below;
 *   tight bullet list.
 * - No color except black and gray.
 *
 * ATS-compatible: all visual elements are real DOM text nodes.
 * Section order: determined by sectionMeta ordering.
 */
export const ResumeMurphy: React.FC<ResumeMurphyProps> = ({
  data,
  showContactIcons = false,
  additionalSectionLabels,
}) => {
  const { personalInfo, summary, workExperience, education, personalProjects, additional } = data;

  const sortedSections = getSortedSections(data);

  // Competency band items (technicalSkills shown in band, not duplicated below)
  const competencyItems = (additional?.technicalSkills ?? []).filter(
    (s): s is string => typeof s === 'string' && s.trim() !== ''
  );

  // ─── Contact helpers ────────────────────────────────────────────────────────

  const contactIcons: Record<string, React.ReactNode> = {
    Email: <Mail size={12} />,
    Phone: <Phone size={12} />,
    Location: <MapPin size={12} />,
    Website: <Globe size={12} />,
    LinkedIn: <Linkedin size={12} />,
    GitHub: <Github size={12} />,
  };

  const renderContactDetail = (label: string, value?: string, hrefPrefix: string = '') => {
    if (!value) return null;

    let finalHrefPrefix = hrefPrefix;
    if (
      ['Website', 'LinkedIn', 'GitHub'].includes(label) &&
      !value.startsWith('http') &&
      !value.startsWith('//')
    ) {
      finalHrefPrefix = 'https://';
    }

    const href = finalHrefPrefix + value;
    const isLink =
      finalHrefPrefix.startsWith('http') ||
      finalHrefPrefix.startsWith('mailto:') ||
      finalHrefPrefix.startsWith('tel:');

    let displayText = value;
    if (isLink && (label === 'LinkedIn' || label === 'GitHub' || label === 'Website')) {
      displayText = value.replace(/^https?:\/\//, '').replace(/^www\./, '');
    }

    return (
      <span className="inline-flex items-center gap-1">
        {showContactIcons && contactIcons[label]}
        {isLink ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline"
            style={{ color: '#cccccc' }}
          >
            {displayText}
          </a>
        ) : (
          <span>{displayText}</span>
        )}
      </span>
    );
  };

  const contactItems = [
    renderContactDetail('Email', personalInfo?.email, 'mailto:'),
    renderContactDetail('Phone', personalInfo?.phone, 'tel:'),
    renderContactDetail('Location', personalInfo?.location),
    renderContactDetail('LinkedIn', personalInfo?.linkedin),
    renderContactDetail('GitHub', personalInfo?.github),
    renderContactDetail('Website', personalInfo?.website),
  ].filter(Boolean);

  // ─── Shared render helpers ──────────────────────────────────────────────────

  const renderBullets = (items?: string[]) => {
    if (!items || items.length === 0) return null;
    return (
      <ul className={`ml-4 ${baseStyles['resume-list']} ${baseStyles['resume-text-sm']}`}>
        {items.map((desc, index) => (
          <li key={index} className="flex">
            <span className="mr-1.5 flex-shrink-0">•&nbsp;</span>
            <span>
              <SafeHtml html={desc} />
            </span>
          </li>
        ))}
      </ul>
    );
  };

  // ─── Section renderer ────────────────────────────────────────────────────────

  const renderSection = (section: SectionMeta) => {
    switch (section.key) {
      case 'personalInfo':
        return null;

      case 'summary':
        if (!summary) return null;
        return (
          <div key={section.id} className={baseStyles['resume-section']}>
            <h3 className={styles.sectionTitle}>{section.displayName}</h3>
            <p className={`text-justify ${baseStyles['resume-text']}`}>{summary}</p>
          </div>
        );

      case 'workExperience':
        if (!workExperience || workExperience.length === 0) return null;
        return (
          <div key={section.id} className={baseStyles['resume-section']}>
            <h3 className={styles.sectionTitle}>{section.displayName}</h3>
            <div className={baseStyles['resume-items']}>
              {workExperience.map((exp) => (
                <div key={exp.id} className={baseStyles['resume-item']}>
                  {/* Row 1: company (bold) left, dates (mono) right */}
                  <div
                    className={`flex justify-between items-baseline gap-3 ${baseStyles['resume-row-tight']}`}
                  >
                    <span className={styles.entryCompany}>{exp.company}</span>
                    {exp.years && (
                      <span className={styles.entryDates}>{formatDateRange(exp.years)}</span>
                    )}
                  </div>
                  {/* Row 2: job title (italic) left, location right */}
                  {(exp.title || exp.location) && (
                    <div
                      className={`flex justify-between items-baseline gap-3 ${baseStyles['resume-row-tight']}`}
                    >
                      {exp.title && <span className={styles.entryRole}>{exp.title}</span>}
                      {exp.location && (
                        <span className={`${baseStyles['resume-date']} shrink-0`}>
                          {exp.location}
                        </span>
                      )}
                    </div>
                  )}
                  {renderBullets(exp.description)}
                </div>
              ))}
            </div>
          </div>
        );

      case 'personalProjects':
        if (!personalProjects || personalProjects.length === 0) return null;
        return (
          <div key={section.id} className={baseStyles['resume-section']}>
            <h3 className={styles.sectionTitle}>{section.displayName}</h3>
            <div className={baseStyles['resume-items']}>
              {personalProjects.map((project) => (
                <div key={project.id} className={baseStyles['resume-item']}>
                  {/* Row 1: project name (bold) left, dates right */}
                  <div
                    className={`flex justify-between items-baseline gap-3 ${baseStyles['resume-row-tight']}`}
                  >
                    <span className="flex items-baseline gap-2 min-w-0">
                      <span className={styles.entryCompany}>{project.name}</span>
                      {project.github && (
                        <a
                          href={
                            project.github.startsWith('http')
                              ? project.github
                              : `https://${project.github}`
                          }
                          target="_blank"
                          rel="noopener noreferrer"
                          className={baseStyles['resume-link-pill']}
                        >
                          <Github size={10} />
                          {project.github
                            .replace(/^https?:\/\//, '')
                            .replace(/^www\./, '')
                            .replace(/\/$/, '')}
                        </a>
                      )}
                      {project.website && (
                        <a
                          href={
                            project.website.startsWith('http')
                              ? project.website
                              : `https://${project.website}`
                          }
                          target="_blank"
                          rel="noopener noreferrer"
                          className={baseStyles['resume-link-pill']}
                        >
                          <ExternalLink size={10} />
                          {project.website
                            .replace(/^https?:\/\//, '')
                            .replace(/^www\./, '')
                            .replace(/\/$/, '')}
                        </a>
                      )}
                    </span>
                    {project.years && (
                      <span className={styles.entryDates}>{formatDateRange(project.years)}</span>
                    )}
                  </div>
                  {/* Row 2: role (italic) */}
                  {project.role && (
                    <div className={baseStyles['resume-row-tight']}>
                      <span className={styles.entryRole}>{project.role}</span>
                    </div>
                  )}
                  {renderBullets(project.description)}
                </div>
              ))}
            </div>
          </div>
        );

      case 'education':
        if (!education || education.length === 0) return null;
        return (
          <div key={section.id} className={baseStyles['resume-section']}>
            <h3 className={styles.sectionTitle}>{section.displayName}</h3>
            <div className={baseStyles['resume-items']}>
              {education.map((edu) => (
                <div key={edu.id} className={baseStyles['resume-item']}>
                  {/* Row 1: institution (bold) left, years right */}
                  <div
                    className={`flex justify-between items-baseline gap-3 ${baseStyles['resume-row-tight']}`}
                  >
                    <span className={styles.entryCompany}>{edu.institution}</span>
                    {edu.years && (
                      <span className={styles.entryDates}>{formatDateRange(edu.years)}</span>
                    )}
                  </div>
                  {/* Row 2: degree (italic) */}
                  {edu.degree && (
                    <div className={baseStyles['resume-row-tight']}>
                      <span className={styles.entryRole}>{edu.degree}</span>
                    </div>
                  )}
                  {edu.description && (
                    <p className={baseStyles['resume-text-sm']}>{edu.description}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        );

      case 'additional':
        if (!additional) return null;
        return (
          <MurphyAdditionalSection
            key={section.id}
            additional={additional}
            displayName={section.displayName}
            labels={additionalSectionLabels}
            // technicalSkills already shown in the competency band — skip here
            skipTechnicalSkills={competencyItems.length > 0}
          />
        );

      default:
        if (!section.isDefault) {
          return (
            <DynamicResumeSectionMurphy
              key={section.id}
              sectionMeta={section}
              resumeData={data}
              renderBullets={renderBullets}
            />
          );
        }
        return null;
    }
  };

  // ─── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className={styles.container}>
      {/* Full-bleed black header bar */}
      {personalInfo && (
        <header className={styles.header}>
          {personalInfo.name && <h1 className={styles.name}>{personalInfo.name}</h1>}
          {contactItems.length > 0 && (
            <div className={styles.contactLine}>
              {contactItems.map((item, index) => (
                <React.Fragment key={index}>
                  {index > 0 && <span className={styles.contactSep}>·</span>}
                  {item}
                </React.Fragment>
              ))}
            </div>
          )}
        </header>
      )}

      {/* Gray competency band — shown only when technicalSkills are present */}
      {competencyItems.length > 0 && (
        <div className={styles.competencyBand} aria-label="Core competencies">
          {competencyItems.map((skill, index) => (
            <React.Fragment key={index}>
              {index > 0 && <span className={styles.competencySep}>|</span>}
              <span>{skill}</span>
            </React.Fragment>
          ))}
        </div>
      )}

      {/* Body sections in sectionMeta order */}
      {sortedSections
        .filter((section) => section.key !== 'personalInfo')
        .map((section) => renderSection(section))}
    </div>
  );
};

// ─── Additional section (languages, certs, awards — NOT technicalSkills) ──────

const MurphyAdditionalSection: React.FC<{
  additional: ResumeData['additional'];
  displayName?: string;
  labels?: Partial<AdditionalSectionLabels>;
  skipTechnicalSkills?: boolean;
}> = ({ additional, displayName = 'Skills & Awards', labels, skipTechnicalSkills = false }) => {
  if (!additional) return null;

  const clean = (items?: string[]) =>
    (items ?? []).filter((item): item is string => typeof item === 'string' && item.trim() !== '');

  const technicalSkills = skipTechnicalSkills ? [] : clean(additional.technicalSkills);
  const languages = clean(additional.languages);
  const certificationsTraining = clean(additional.certificationsTraining);
  const awards = clean(additional.awards);

  const mergedLabels: AdditionalSectionLabels = {
    technicalSkills: labels?.technicalSkills ?? 'Technical Skills:',
    languages: labels?.languages ?? 'Languages:',
    certifications: labels?.certifications ?? 'Certifications:',
    awards: labels?.awards ?? 'Awards:',
  };

  const hasContent =
    technicalSkills.length > 0 ||
    languages.length > 0 ||
    certificationsTraining.length > 0 ||
    awards.length > 0;

  if (!hasContent) return null;

  const line = (label: string, items: string[]) =>
    items.length > 0 ? (
      <div className="flex">
        <span className={styles.skillLabel}>{label}</span>
        <span>{items.join(', ')}</span>
      </div>
    ) : null;

  return (
    <div className={baseStyles['resume-section']}>
      <h3 className={styles.sectionTitle}>{displayName}</h3>
      <div className={`${baseStyles['resume-stack']} ${baseStyles['resume-text-sm']}`}>
        {line(mergedLabels.technicalSkills, technicalSkills)}
        {line(mergedLabels.languages, languages)}
        {line(mergedLabels.certifications, certificationsTraining)}
        {line(mergedLabels.awards, awards)}
      </div>
    </div>
  );
};

// ─── Dynamic (custom) section wrapper ─────────────────────────────────────────

const DynamicResumeSectionMurphy: React.FC<{
  sectionMeta: SectionMeta;
  resumeData: ResumeData;
  renderBullets: (items?: string[]) => React.ReactNode;
}> = ({ sectionMeta, resumeData, renderBullets }) => {
  const customSection = resumeData.customSections?.[sectionMeta.key];
  if (!customSection) return null;

  const hasContent = (() => {
    switch (sectionMeta.sectionType) {
      case 'text':
        return Boolean(customSection.text?.trim());
      case 'itemList':
        return Boolean(customSection.items?.length);
      case 'stringList':
        return Boolean(customSection.strings?.length);
      default:
        return false;
    }
  })();

  if (!hasContent) return null;

  return (
    <div className={baseStyles['resume-section']}>
      <h3 className={styles.sectionTitle}>{sectionMeta.displayName}</h3>
      {sectionMeta.sectionType === 'text' && customSection.text?.trim() && (
        <p className={`text-justify ${baseStyles['resume-text']}`}>{customSection.text}</p>
      )}
      {sectionMeta.sectionType === 'itemList' && customSection.items?.length ? (
        <div className={baseStyles['resume-items']}>
          {customSection.items.map((item) => (
            <div key={item.id} className={baseStyles['resume-item']}>
              <div
                className={`flex justify-between items-baseline gap-3 ${baseStyles['resume-row-tight']}`}
              >
                <span className={styles.entryCompany}>{item.title}</span>
                {item.years && (
                  <span className={styles.entryDates}>{formatDateRange(item.years)}</span>
                )}
              </div>
              {(item.subtitle || item.location) && (
                <div
                  className={`flex justify-between items-baseline gap-3 ${baseStyles['resume-row-tight']}`}
                >
                  {item.subtitle && <span className={styles.entryRole}>{item.subtitle}</span>}
                  {item.location && (
                    <span className={`${baseStyles['resume-date']} shrink-0`}>{item.location}</span>
                  )}
                </div>
              )}
              {renderBullets(item.description)}
            </div>
          ))}
        </div>
      ) : null}
      {sectionMeta.sectionType === 'stringList' && customSection.strings?.length ? (
        <div className={baseStyles['resume-text-sm']}>{customSection.strings.join(', ')}</div>
      ) : null}
    </div>
  );
};

export default ResumeMurphy;
