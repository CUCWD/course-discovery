from django.utils.translation import ugettext_lazy as _
from djchoices import ChoiceItem, DjangoChoices


class SimulationStatus(DjangoChoices):
    Published = ChoiceItem('published', _('Published'))
    Unpublished = ChoiceItem('unpublished', _('Unpublished'))


class SimulationMode(DjangoChoices):
    # Translators: Augmented reality refers to an interactive experience of a real-world environment where the
    # objects that reside in the real-world are "augmented" by computer-generated perceptual information, sometimes
    # across multiple sensory modalities, including visual, auditory, haptic, somatosensory, and olfactory.
    # This reality may also be considered a form of VR that layers virtual information over a live camera feed into a
    # headset or through a smartphone or tablet device giving the user the ability to view three-dimensional images.
    Augmented = ChoiceItem('augmented', _('Augmented'))
    # Translators: Desktop refers to an interactive experience that does not need headset to be fully-immersive
    # experience and can be performed with keyboard/mouse interaction.
    Desktop = ChoiceItem('desktop', _('Desktop'))
    # Translators: An interactive computer-generated experience taking place within a simulated environment. It
    # incorporates mainly auditory and visual feedback, but may also allow other types of sensory feedback like
    # haptic. This immersive environment can be similar to the real world or it can be fantastical.
    Immersive = ChoiceItem('immersive', _('Immersive'))
    # Translators: sometimes referred to as hybrid reality,[1] is the merging of real and virtual worlds to produce
    # new environments and visualizations where physical and digital objects co-exist and interact in real time.
    # Mixed reality takes place not only in the physical world or the virtual world,[1] but is a mix of reality and
    # virtual reality, encompassing both augmented reality and augmented virtuality[2] via immersive technology.
    Mixed = ChoiceItem('mixed', _('Mixed'))


class SequentialStatus(DjangoChoices):
    Published = ChoiceItem('published', _('Published'))
    Unpublished = ChoiceItem('unpublished', _('Unpublished'))


class ChapterStatus(DjangoChoices):
    Published = ChoiceItem('published', _('Published'))
    Unpublished = ChoiceItem('unpublished', _('Unpublished'))


class CourseRunStatus(DjangoChoices):
    Published = ChoiceItem('published', _('Published'))
    Unpublished = ChoiceItem('unpublished', _('Unpublished'))


class CourseRunPacing(DjangoChoices):
    # Translators: Instructor-paced refers to course runs that operate on a schedule set by the instructor,
    # similar to a normal university course.
    Instructor = ChoiceItem('instructor_paced', _('Instructor-paced'))
    # Translators: Self-paced refers to course runs that operate on the student's schedule.
    Self = ChoiceItem('self_paced', _('Self-paced'))


class ProgramStatus(DjangoChoices):
    Unpublished = ChoiceItem('unpublished', _('Unpublished'))
    Active = ChoiceItem('active', _('Active'))
    Retired = ChoiceItem('retired', _('Retired'))
    Deleted = ChoiceItem('deleted', _('Deleted'))


class ReportingType(DjangoChoices):
    mooc = ChoiceItem('mooc', 'mooc')
    spoc = ChoiceItem('spoc', 'spoc')
    test = ChoiceItem('test', 'test')
    demo = ChoiceItem('demo', 'demo')
    other = ChoiceItem('other', 'other')
